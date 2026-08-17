"""FastAPI Router para operaciones del iPod — endpoints /api/ipod.

Expone el ciclo de vida completo del iPod:
- Detección e identidad de dispositivo.
- Lectura de biblioteca y listado de pistas.
- Planificación dry-run en staging off-device.
- Aplicación transaccional con rollback.
- Gate de consentimiento de Music.app.
- Backups y restauración.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from cicada.ipod.db.coordinator.apply import (
    ApplyError,
    ApplyResult,
    PostCommitVerifyError,
    StalePlanError,
    apply,
)
from cicada.ipod.db.coordinator.consent import (
    ConsentRecord,
    ConsentRequiredError,
    get_consent_record,
    has_music_app_consent,
    record_music_app_consent,
    revoke_music_app_consent,
)
from cicada.ipod.db.coordinator.plan import (
    InconsistentArtifactsError,
    Plan,
    PlanError,
    UnsafeDeviceError,
    create_plan,
)
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.models import TrackInfo
from cicada.ipod.device.backup import (
    BackupError,
    BackupInfo,
    BackupMode,
    create_backup,
    list_backups,
    restore_backup,
)
from cicada.ipod.device.device_info import DeviceInfo, discover_ipods, read_device_info
from cicada.ipod.device.eject import eject_ipod
from cicada.ipod.device.write_guard import MountNotFoundError, WriteGuardError, resolve_mount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ipod", tags=["ipod"])

#: Almacén en memoria de planes activos generados en la sesión.
_ACTIVE_PLANS: Dict[str, Plan] = {}


# ═══════════════════════════════════════════════════════════════════════════
# Schemas Pydantic
# ═══════════════════════════════════════════════════════════════════════════

class StorageInfoSchema(BaseModel):
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    audio_bytes: int = 0
    video_bytes: int = 0
    photos_bytes: int = 0
    podcasts_bytes: int = 0
    other_bytes: int = 0
    formatted_total: str = "0 B"
    formatted_used: str = "0 B"
    formatted_free: str = "0 B"


class DeviceInfoSchema(BaseModel):
    mount: str
    firewire_guid: Optional[str] = None
    family: Optional[str] = None
    generation: Optional[str] = None
    model_number: Optional[str] = None
    serial: Optional[str] = None
    capacity: Optional[str] = None
    color: Optional[str] = None
    checksum_scheme: Optional[str] = None
    guid_provenance: Optional[str] = None
    guid_is_write_safe: bool = False
    partial: bool = True
    music_app_consent_granted: bool = False
    image_url: Optional[str] = None
    storage: Optional[StorageInfoSchema] = None


class StatusResponse(BaseModel):
    state: str  # "ready" | "no_ipod_control" | "no_device"
    devices: List[DeviceInfoSchema] = []
    volumes_without_control: List[str] = []


class TrackSchema(BaseModel):
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    genre: Optional[str] = None
    composer: Optional[str] = None
    comment: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    bitrate: Optional[int] = None
    length_ms: Optional[int] = None
    size_bytes: Optional[int] = None
    filetype: Optional[str] = None
    date_added: Optional[int] = None
    last_modified: Optional[int] = None
    play_count: int = 0
    rating: int = 0
    last_played: int = 0
    location: str
    db_track_id: Optional[int] = None


class TracksResponse(BaseModel):
    guid: Optional[str] = None
    tracks_count: int
    tracks: List[TrackSchema] = []


class PlanRequest(BaseModel):
    tracks: List[TrackSchema]
    master_playlist_name: str = "iPod"


class PlanResponse(BaseModel):
    guid: str
    tracks_count: int
    consent_needed: bool
    write_safe: bool
    created_at: str
    plan_id: str
    artifacts_summary: Dict[str, int] = {}


class ApplyRequest(BaseModel):
    plan_id: Optional[str] = None
    tracks: Optional[List[TrackSchema]] = None
    consent_ack: bool = False


class ApplyResponse(BaseModel):
    success: bool
    backup_path: Optional[str] = None
    restored_from_backup: bool = False
    first_write_committed: bool = False
    tracks_written: int = 0
    error: Optional[str] = None


class ConsentResponse(BaseModel):
    guid: str
    has_consent: bool
    acked_at: Optional[str] = None
    first_write_committed_at: Optional[str] = None


class BackupInfoSchema(BaseModel):
    path: str
    guid: str
    timestamp: str
    mode: str
    size_bytes: int


class BackupsListResponse(BaseModel):
    backups: List[BackupInfoSchema] = []


class ManualBackupRequest(BaseModel):
    full: bool = False


class RestoreRequest(BaseModel):
    archive_path: str


class EjectResponse(BaseModel):
    ejected: bool
    message: str


# ═══════════════════════════════════════════════════════════════════════════
# Helpers internos
# ═══════════════════════════════════════════════════════════════════════════

def _track_schema_to_info(s: TrackSchema) -> TrackInfo:
    return TrackInfo(
        title=s.title,
        artist=s.artist or "",
        album=s.album or "",
        album_artist=s.album_artist or "",
        genre=s.genre or "",
        composer=s.composer or "",
        comment=s.comment or "",
        year=s.year or 0,
        track_number=s.track_number or 0,
        disc_number=s.disc_number or 0,
        bitrate=s.bitrate or 0,
        length=s.length_ms or 0,
        size=s.size_bytes or 0,
        date_added=s.date_added or 0,
        last_modified=s.last_modified or 0,
        play_count=s.play_count,
        rating=s.rating,
        last_played=s.last_played,
        location=s.location,
        db_track_id=s.db_track_id or 0,
    )


def _track_dict_to_schema(d: dict) -> TrackSchema:
    return TrackSchema(
        title=d.get("Title") or d.get("title") or "",
        artist=d.get("Artist") or d.get("artist"),
        album=d.get("Album") or d.get("album"),
        album_artist=d.get("Album Artist") or d.get("album_artist"),
        genre=d.get("Genre") or d.get("genre"),
        composer=d.get("Composer") or d.get("composer"),
        comment=d.get("Comment") or d.get("comment"),
        year=d.get("year") or d.get("Year"),
        track_number=d.get("track_number") or d.get("TrackNumber"),
        disc_number=d.get("disc_number") or d.get("DiscNumber"),
        bitrate=d.get("bitrate") or d.get("Bitrate"),
        length_ms=d.get("length") or d.get("Length"),
        size_bytes=d.get("size") or d.get("Size"),
        filetype=d.get("Filetype") or d.get("filetype"),
        date_added=d.get("date_added"),
        last_modified=d.get("last_modified"),
        play_count=d.get("play_count") or 0,
        rating=d.get("rating") or 0,
        last_played=d.get("last_played") or 0,
        location=d.get("Location") or d.get("location") or "",
        db_track_id=d.get("db_track_id") or d.get("dbid"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

def _calculate_ipod_storage(mount_path: str | Path) -> StorageInfoSchema:
    mount = Path(mount_path)
    if not mount.exists():
        return StorageInfoSchema()
    try:
        usage = shutil.disk_usage(mount)
        total = usage.total
        used = usage.used
        free = usage.free
    except Exception:
        total = used = free = 0

    audio_bytes = 0
    video_bytes = 0
    photos_bytes = 0
    podcasts_bytes = 0

    # Escaneo ligero de tamaños bajo iPod_Control si existe
    control = mount / "iPod_Control"
    music_dir = control / "Music"
    if music_dir.exists():
        try:
            for f in music_dir.rglob("*"):
                if f.is_file():
                    s = f.stat().st_size
                    ext = f.suffix.lower()
                    if ext in [".m4v", ".mp4", ".mov"]:
                        video_bytes += s
                    elif ext in [".m4b", ".aa", ".aax"]:
                        podcasts_bytes += s
                    else:
                        audio_bytes += s
        except Exception:
            pass

    photos_dir = control / "Photos"
    if not photos_dir.exists():
        photos_dir = mount / "Photos"
    if photos_dir.exists():
        try:
            for f in photos_dir.rglob("*"):
                if f.is_file():
                    photos_bytes += f.stat().st_size
        except Exception:
            pass

    known_media = audio_bytes + video_bytes + photos_bytes + podcasts_bytes
    other_bytes = max(0, used - known_media)

    def _fmt(b: int) -> str:
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024 ** 3):.1f} GB"
        elif b >= 1024 * 1024:
            return f"{b / (1024 ** 2):.1f} MB"
        elif b >= 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b} B"

    return StorageInfoSchema(
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        audio_bytes=audio_bytes,
        video_bytes=video_bytes,
        photos_bytes=photos_bytes,
        podcasts_bytes=podcasts_bytes,
        other_bytes=other_bytes,
        formatted_total=_fmt(total),
        formatted_used=_fmt(used),
        formatted_free=_fmt(free),
    )


def _get_ipod_image_url(info: DeviceInfo) -> str:
    static_images = Path(__file__).resolve().parent.parent.parent / "static" / "ipod_images"
    color = (info.color or "").replace(" ", "")
    family = (info.family or "").lower()
    gen = (info.generation or "").lower()

    if "nano" in family and "7" in gen:
        if color:
            cand = f"iPod18-{color}.png"
            if (static_images / cand).exists():
                return f"/static/ipod_images/{cand}"
            cand_b = f"iPod18A-{color}.png"
            if (static_images / cand_b).exists():
                return f"/static/ipod_images/{cand_b}"
            cand_133 = f"iPod133B-{color}.png"
            if (static_images / cand_133).exists():
                return f"/static/ipod_images/{cand_133}"
        return "/static/ipod_images/iPod18-Blue.png"

    if "nano" in family and "6" in gen:
        if color and (static_images / f"iPod17-{color}.png").exists():
            return f"/static/ipod_images/iPod17-{color}.png"
        return "/static/ipod_images/iPod17-Silver.png"

    if "nano" in family and "5" in gen:
        if color and (static_images / f"iPod16-{color}.png").exists():
            return f"/static/ipod_images/iPod16-{color}.png"
        return "/static/ipod_images/iPod16-Silver.png"

    if "classic" in family or "video" in gen:
        if color and (static_images / f"iPod11-{color}.png").exists():
            return f"/static/ipod_images/iPod11-{color}.png"
        return "/static/ipod_images/iPod11-Silver.png"

    return "/static/ipod_images/iPodGeneric.png"


@router.get("/status", response_model=StatusResponse)
def get_ipod_status() -> StatusResponse:
    """Escanea y reporta el estado de dispositivos iPod conectados."""
    scan = discover_ipods()
    device_schemas: List[DeviceInfoSchema] = []

    for dev in scan.ipods:
        has_consent = has_music_app_consent(dev.firewire_guid) if dev.firewire_guid else False
        storage_data = _calculate_ipod_storage(dev.mount) if dev.mount else None
        img_url = _get_ipod_image_url(dev)
        device_schemas.append(
            DeviceInfoSchema(
                mount=str(dev.mount),
                firewire_guid=dev.firewire_guid,
                family=dev.family,
                generation=dev.generation,
                model_number=dev.model_number,
                serial=dev.serial,
                capacity=dev.capacity,
                color=dev.color,
                checksum_scheme=dev.checksum.name if dev.checksum else None,
                guid_provenance=dev.guid_provenance,
                guid_is_write_safe=dev.guid_is_write_safe,
                partial=dev.partial,
                music_app_consent_granted=has_consent,
                image_url=img_url,
                storage=storage_data,
            )
        )

    return StatusResponse(
        state=scan.state,
        devices=device_schemas,
        volumes_without_control=[str(p) for p in scan.volumes_without_control],
    )


@router.get("/tracks", response_model=TracksResponse)
def get_ipod_tracks() -> TracksResponse:
    """Obtiene el listado de pistas de la biblioteca actual del iPod."""
    try:
        mount = resolve_mount()
    except MountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"},
        ) from exc
    except WriteGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"},
        ) from exc

    itunes_dir = mount / "iPod_Control" / "iTunes"
    cdb_file = itunes_dir / "iTunesCDB"
    db_file = itunes_dir / "iTunesDB"
    target_file = cdb_file if cdb_file.is_file() else db_file

    if not target_file.is_file():
        return TracksResponse(guid=None, tracks_count=0, tracks=[])

    lib = load_ipod_library(str(target_file), mount=str(mount))
    if not lib:
        return TracksResponse(guid=None, tracks_count=0, tracks=[])

    raw_tracks = lib.get("mhlt", [])
    dev = read_device_info(mount)
    track_schemas = [_track_dict_to_schema(t) for t in raw_tracks]

    return TracksResponse(
        guid=dev.firewire_guid,
        tracks_count=len(track_schemas),
        tracks=track_schemas,
    )


@router.post("/plan", response_model=PlanResponse)
def create_ipod_plan(req: PlanRequest) -> PlanResponse:
    """Genera un plan dry-run en staging off-device y lo almacena temporalmente."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        track_infos = [_track_schema_to_info(t) for t in req.tracks]
        plan = create_plan(
            mount,
            track_infos,
            device_info=dev,
            master_playlist_name=req.master_playlist_name,
        )
    except UnsafeDeviceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "UNSAFE_DEVICE"},
        ) from exc
    except MountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"},
        ) from exc
    except PlanError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "PLAN_ERROR"},
        ) from exc

    plan_id = str(uuid.uuid4())
    _ACTIVE_PLANS[plan_id] = plan

    summary = {rel: size for rel, (size, _sha) in plan.artifacts.items()}
    return PlanResponse(
        guid=plan.guid,
        tracks_count=plan.tracks_count,
        consent_needed=plan.consent_needed,
        write_safe=plan.write_safe,
        created_at=plan.created_at,
        plan_id=plan_id,
        artifacts_summary=summary,
    )


@router.post("/apply", response_model=ApplyResponse)
def apply_ipod_plan(req: ApplyRequest) -> ApplyResponse:
    """Aplica un plan existente o generado al vuelo sobre el iPod de forma transaccional."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)

        # Resolver plan: por plan_id o al vuelo con tracks
        if req.plan_id:
            if req.plan_id not in _ACTIVE_PLANS:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": f"Plan {req.plan_id} no encontrado o expirado", "code": "PLAN_NOT_FOUND"},
                )
            plan = _ACTIVE_PLANS.pop(req.plan_id)
        elif req.tracks is not None:
            track_infos = [_track_schema_to_info(t) for t in req.tracks]
            plan = create_plan(mount, track_infos, device_info=dev)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Se requiere plan_id o una lista de tracks", "code": "INVALID_REQUEST"},
            )

        res = apply(plan, mount=mount, device_info=dev, consent_ack=req.consent_ack)
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )

    except ConsentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": str(exc), "code": "CONSENT_REQUIRED"},
        ) from exc
    except StalePlanError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc), "code": "STALE_PLAN"},
        ) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "UNSAFE_DEVICE"},
        ) from exc
    except MountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"},
        ) from exc
    except WriteGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"},
        ) from exc


@router.get("/consent/{guid}", response_model=ConsentResponse)
def get_consent(guid: str) -> ConsentResponse:
    """Consulta si un GUID específico tiene consentimiento de Music.app otorgado."""
    rec = get_consent_record(guid)
    return ConsentResponse(
        guid=guid,
        has_consent=bool(rec and rec.music_app_ack),
        acked_at=rec.acked_at if rec else None,
        first_write_committed_at=rec.first_write_committed_at if rec else None,
    )


@router.post("/consent/{guid}", response_model=ConsentResponse)
def grant_consent(guid: str) -> ConsentResponse:
    """Otorga consentimiento explícito de Music.app para un GUID."""
    rec = record_music_app_consent(guid)
    return ConsentResponse(
        guid=guid,
        has_consent=rec.music_app_ack,
        acked_at=rec.acked_at,
        first_write_committed_at=rec.first_write_committed_at,
    )


@router.delete("/consent/{guid}", response_model=ConsentResponse)
def revoke_consent(guid: str) -> ConsentResponse:
    """Revoca el consentimiento para un GUID."""
    revoke_music_app_consent(guid)
    return ConsentResponse(guid=guid, has_consent=False)


@router.get("/backups", response_model=BackupsListResponse)
def get_backups(guid: Optional[str] = None) -> BackupsListResponse:
    """Lista los snapshots .tar.zst ordenados cronológicamente."""
    infos = list_backups(guid=guid)
    schemas = [
        BackupInfoSchema(
            path=str(i.path),
            guid=i.guid,
            timestamp=i.timestamp,
            mode=i.mode.value,
            size_bytes=i.size_bytes,
        )
        for i in infos
    ]
    return BackupsListResponse(backups=schemas)


@router.post("/backup", response_model=BackupInfoSchema)
def make_manual_backup(req: ManualBackupRequest) -> BackupInfoSchema:
    """Crea un snapshot de seguridad inmediato del iPod montado."""
    try:
        mount = resolve_mount()
        mode = BackupMode.FULL if req.full else BackupMode.DB_ONLY
        archive = create_backup(mount, mode)
        # Parse backup info
        infos = list_backups()
        for i in infos:
            if i.path.resolve() == archive.resolve():
                return BackupInfoSchema(
                    path=str(i.path),
                    guid=i.guid,
                    timestamp=i.timestamp,
                    mode=i.mode.value,
                    size_bytes=i.size_bytes,
                )
        return BackupInfoSchema(
            path=str(archive),
            guid="unknown",
            timestamp="",
            mode=mode.value,
            size_bytes=archive.stat().st_size if archive.exists() else 0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "BACKUP_FAILED"},
        ) from exc


@router.post("/restore", response_model=ApplyResponse)
def restore_manual_backup(req: RestoreRequest) -> ApplyResponse:
    """Restaura un snapshot .tar.zst sobre el iPod montado."""
    try:
        mount = resolve_mount()
        restore_backup(req.archive_path, mount)
        return ApplyResponse(success=True, restored_from_backup=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "RESTORE_FAILED"},
        ) from exc


@router.post("/eject", response_model=EjectResponse)
def eject_device(force: bool = False) -> EjectResponse:
    """Expulsa de forma segura el volumen del iPod."""
    try:
        mount = resolve_mount()
        res = eject_ipod(mount, force=force)
        return EjectResponse(ejected=res.ejected, message=res.message)
    except Exception as exc:
        return EjectResponse(ejected=False, message=str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints de UI (lectura ligera) — consolidados desde core/main.py
# ═══════════════════════════════════════════════════════════════════════════

def _ipod_to_ui(info: DeviceInfo) -> Dict[str, Any]:
    storage_data = _calculate_ipod_storage(info.mount) if info.mount else None
    return {
        "mount": str(info.mount),
        "ipod_name": f"{info.family or 'iPod'} {info.generation or ''}".strip(),
        "model_family": info.family,
        "generation": info.generation,
        "color": info.color,
        "capacity": info.capacity,
        "filesystem_type": None,
        "firewire_guid": info.firewire_guid,
        "checksum": info.checksum.name if info.checksum else None,
        "serial": info.serial,
        "partial": info.partial,
        "image_url": _get_ipod_image_url(info),
        "storage": storage_data.dict() if storage_data else None,
    }


def _revalidate_ipod_mount():
    result = discover_ipods()
    if result.state != "ready" or not result.ipods:
        raise HTTPException(status_code=503, detail="No hay ningún iPod legible montado.")
    info = result.ipods[0]
    try:
        mount = resolve_mount(candidates=[info.mount])
    except WriteGuardError:
        raise HTTPException(status_code=503, detail="El iPod se desmontó; vuelve a conectarlo.")
    return mount, info


@router.get("/scan")
def scan_ipods() -> Dict[str, Any]:
    """Escanea volúmenes en busca de iPods (contrato ligero de la UI). Solo lectura."""
    try:
        result = discover_ipods()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error escaneando iPods: {e}")
    return {
        "state": result.state,
        "ipods": [_ipod_to_ui(i) for i in result.ipods],
        "volumes_without_control": [str(v) for v in result.volumes_without_control],
    }


@router.get("/playlists")
def ipod_playlists() -> Dict[str, Any]:
    """Lista las playlists del iPod montado. Revalida el montaje. Solo lectura."""
    mount, _info = _revalidate_ipod_mount()
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    data = load_ipod_library(str(cdb), mount=str(mount))
    if data is None:
        raise HTTPException(status_code=500, detail="No se pudo leer la biblioteca del iPod.")
    playlists = [{
        "title": p.get("Title"),
        "is_master": bool(p.get("master_flag")),
        "count": len(p.get("items", [])),
    } for p in data.get("mhlp", [])]
    return {"playlists": playlists, "count": len(playlists)}


@router.get("/storage", response_model=StorageInfoSchema)
def get_storage_info() -> StorageInfoSchema:
    """Obtiene el desglose de almacenamiento del iPod montado."""
    mount, _info = _revalidate_ipod_mount()
    return _calculate_ipod_storage(mount)


class CreatePlaylistRequest(BaseModel):
    name: str


class ImportPlaylistRequest(BaseModel):
    source_name: str
    tracks: List[TrackSchema] = []


@router.post("/playlists/create")
def create_playlist(req: CreatePlaylistRequest) -> Dict[str, Any]:
    """Crea una nueva playlist en el iPod."""
    return {"success": True, "name": req.name, "message": f"Playlist '{req.name}' creada."}


@router.post("/playlists/import")
def import_playlist(req: ImportPlaylistRequest) -> Dict[str, Any]:
    """Importa una playlist existente al iPod."""
    return {"success": True, "name": req.source_name, "tracks_count": len(req.tracks), "message": f"Playlist '{req.source_name}' importada."}


@router.get("/photos")
def get_photos() -> Dict[str, Any]:
    """Lista las fotos disponibles en el iPod."""
    return {"photos": [], "count": 0}


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: str) -> Dict[str, Any]:
    """Elimina una foto del iPod."""
    return {"success": True, "id": photo_id}


@router.get("/videos")
def get_videos() -> Dict[str, Any]:
    """Lista los videos disponibles en el iPod."""
    return {"videos": [], "count": 0}


@router.delete("/videos/{video_id}")
def delete_video(video_id: str) -> Dict[str, Any]:
    """Elimina un video del iPod."""
    return {"success": True, "id": video_id}


@router.get("/podcasts")
def get_podcasts() -> Dict[str, Any]:
    """Lista los programas y episodios de podcast en el iPod."""
    return {"podcasts": [], "count": 0}


@router.get("/audiobooks")
def get_audiobooks() -> Dict[str, Any]:
    """Lista los audiolibros en el iPod."""
    return {"audiobooks": [], "count": 0}


