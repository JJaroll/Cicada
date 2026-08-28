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
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from cicada.shared.artwork import extract_embedded_artwork

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
from cicada.ipod.db.shared.constants import (
    MEDIA_TYPE_AUDIOBOOK,
    MEDIA_TYPE_MUSIC_VIDEO,
    MEDIA_TYPE_PODCAST,
    MEDIA_TYPE_TV_SHOW,
    MEDIA_TYPE_TV_SHOW_ALT,
    MEDIA_TYPE_VIDEO,
    MEDIA_TYPE_VIDEO_PODCAST,
)
from cicada.ipod.db.coordinator.media import (
    delete_ipod_playlist,
    preserve_existing_playlists,
    remove_track_from_ipod,
    set_ipod_playlist,
    sync_media_to_ipod,
    update_ipod_playlist,
)
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
from cicada.ipod.sync.bidirectional import sync_playback_stats
from cicada.ipod.sync.conflicts import resolve_conflicts, scan_for_conflicts
from cicada.ipod.sync.state import DeviceRecord, LocalPlaybackStateRecord, SyncStateDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ipod", tags=["ipod"])

_ACTIVE_PLANS: Dict[str, Plan] = {}


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
    state: str
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
    db_track_id: Optional[str] = None
    media_type: Optional[int] = None
    is_podcast: bool = False
    is_audiobook: bool = False
    is_video: bool = False


class TracksResponse(BaseModel):
    guid: Optional[str] = None
    tracks_count: int
    tracks: List[TrackSchema] = []


class PodcastEpisodeSchema(BaseModel):
    id: Optional[str] = None
    title: str
    date_added: Optional[int] = None
    duration_ms: Optional[int] = None
    file_size: Optional[int] = None


class PodcastSchema(BaseModel):
    id: str
    name: str
    episodes: List[PodcastEpisodeSchema] = []


class PodcastsResponse(BaseModel):
    podcasts: List[PodcastSchema] = []
    count: int


class AudiobookChapterSchema(BaseModel):
    id: Optional[str] = None
    title: str
    duration_ms: Optional[int] = None


class AudiobookSchema(BaseModel):
    id: str
    title: str
    author: Optional[str] = None
    chapters: List[AudiobookChapterSchema] = []
    db_track_ids: List[str] = []


class AudiobooksResponse(BaseModel):
    audiobooks: List[AudiobookSchema] = []
    count: int


class VideoSchema(BaseModel):
    id: str
    title: str
    kind: str
    duration_ms: Optional[int] = None
    size_bytes: Optional[int] = None
    show_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    thumb: Optional[str] = None


class VideosResponse(BaseModel):
    videos: List[VideoSchema] = []
    count: int


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
    artwork_touched: bool = False
    artwork_tracks_count: int = 0
    artwork_skipped_count: int = 0


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
    artwork_touched: bool = False
    artwork_tracks_count: int = 0
    artwork_skipped_count: int = 0


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
        db_track_id=int(s.db_track_id) if s.db_track_id else 0,
    )


def _track_dict_to_schema(d: dict) -> TrackSchema:
    mt = d.get("media_type") or 0
    podcast_flag = d.get("podcast_flag") or 0
    movie_flag = d.get("movie_flag") or d.get("movie_flag_2") or 0
    ft = (d.get("Filetype") or d.get("filetype") or "").lower()
    loc = (d.get("Location") or d.get("location") or "").lower()
    genre = (d.get("Genre") or d.get("genre") or "").lower()

    is_podcast = bool(
        podcast_flag == 1
        or (mt & MEDIA_TYPE_PODCAST) != 0
        or mt == MEDIA_TYPE_VIDEO_PODCAST
        or genre == "podcast"
    )
    is_audiobook = bool(
        (mt & MEDIA_TYPE_AUDIOBOOK) != 0
        or mt == MEDIA_TYPE_AUDIOBOOK
        or ft == "m4b"
        or loc.endswith(".m4b")
        or genre in ("audiobook", "audiolibro", "audiobooks", "audiolibros")
    )
    is_video = bool(
        mt in _VIDEO_MEDIA_TYPES
        or (mt & (MEDIA_TYPE_VIDEO | MEDIA_TYPE_MUSIC_VIDEO | MEDIA_TYPE_TV_SHOW)) != 0
        or movie_flag == 1
        or ft in ("m4v", "mp4", "mov")
        or loc.endswith((".m4v", ".mp4", ".mov"))
    )

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
        db_track_id=str(d.get("db_track_id") or d.get("dbid") or "") or None,
        media_type=mt or None,
        is_podcast=is_podcast,
        is_audiobook=is_audiobook,
        is_video=is_video,
    )


def _load_current_library(mount: Path) -> Optional[dict]:
    """Carga la biblioteca actual del iPod (iTunesCDB/iTunesDB), o ``None``
    si el dispositivo todavía no tiene una base escrita."""
    itunes_dir = mount / "iPod_Control" / "iTunes"
    cdb_file = itunes_dir / "iTunesCDB"
    db_file = itunes_dir / "iTunesDB"
    target_file = cdb_file if cdb_file.is_file() else db_file
    if not target_file.is_file():
        return None
    return load_ipod_library(str(target_file), mount=str(mount)) or None


def _slugify(name: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "sin-titulo"


def _group_tracks_by(tracks: List[dict], media_types: int | frozenset[int]) -> Dict[str, List[dict]]:
    """Agrupa pistas de uno o más ``media_type`` por Album (nombre del
    programa/libro), con fallback a Artist y luego a un cajón único si
    ninguno está presente."""
    wanted = {media_types} if isinstance(media_types, int) else media_types
    groups: Dict[str, List[dict]] = {}
    for t in tracks:
        if t.get("media_type") not in wanted:
            continue
        name = (t.get("Album") or t.get("Artist") or "").strip() or "Sin título"
        groups.setdefault(name, []).append(t)
    return groups


_VIDEO_MEDIA_TYPES = frozenset({
    MEDIA_TYPE_VIDEO, MEDIA_TYPE_MUSIC_VIDEO, MEDIA_TYPE_TV_SHOW, MEDIA_TYPE_TV_SHOW_ALT,
})

_VIDEO_KIND_LABELS = {
    MEDIA_TYPE_VIDEO: "movie",
    MEDIA_TYPE_MUSIC_VIDEO: "music_video",
    MEDIA_TYPE_TV_SHOW: "tv_show",
    MEDIA_TYPE_TV_SHOW_ALT: "tv_show",
}


def _video_kind_label(media_type: int) -> str:
    return _VIDEO_KIND_LABELS.get(media_type, "movie")


def _chapter_durations_ms(chapters: List[dict], track_length_ms: int) -> List[int]:
    """Duración de cada capítulo a partir de los ``startpos`` consecutivos
    (chapter_data solo trae posición de inicio, no duración) — el último
    capítulo dura hasta el final de la pista."""
    durations = []
    for i, ch in enumerate(chapters):
        start = ch.get("startpos", 0)
        end = chapters[i + 1].get("startpos", start) if i + 1 < len(chapters) else track_length_ms
        durations.append(max(0, end - start))
    return durations


_STORAGE_CACHE: Dict[str, tuple[float, StorageInfoSchema]] = {}
_STORAGE_TTL_SECONDS = 60.0


def _calculate_ipod_storage(mount_path: str | Path) -> StorageInfoSchema:
    """Desglose de storage con caché de TTL corto: evita recorrer el FS del iPod
    en cada /status o /scan (el desglose cambia poco entre escrituras)."""
    key = str(mount_path)
    cached = _STORAGE_CACHE.get(key)
    if cached is not None and (time.monotonic() - cached[0]) < _STORAGE_TTL_SECONDS:
        return cached[1]
    result = _compute_ipod_storage(mount_path)
    _STORAGE_CACHE[key] = (time.monotonic(), result)
    return result


def _compute_ipod_storage(mount_path: str | Path) -> StorageInfoSchema:
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

    lib = _load_current_library(mount)
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
        regular, smart = preserve_existing_playlists(mount)
        plan = create_plan(
            mount,
            track_infos,
            device_info=dev,
            master_playlist_name=req.master_playlist_name,
            playlists=regular or None,
            smart_playlists=smart or None,
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
        artwork_touched=plan.artwork_touched,
        artwork_tracks_count=plan.artwork_tracks_count,
        artwork_skipped_count=plan.artwork_skipped_count,
    )


@router.post("/apply", response_model=ApplyResponse)
def apply_ipod_plan(req: ApplyRequest) -> ApplyResponse:
    """Aplica un plan existente o generado al vuelo sobre el iPod de forma transaccional."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)

        if req.plan_id:
            if req.plan_id not in _ACTIVE_PLANS:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": f"Plan {req.plan_id} no encontrado o expirado", "code": "PLAN_NOT_FOUND"},
                )
            plan = _ACTIVE_PLANS.pop(req.plan_id)
        elif req.tracks is not None:
            track_infos = [_track_schema_to_info(t) for t in req.tracks]
            regular, smart = preserve_existing_playlists(mount)
            plan = create_plan(mount, track_infos, device_info=dev,
                               playlists=regular or None, smart_playlists=smart or None)
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
            artwork_touched=res.artwork_touched,
            artwork_tracks_count=res.artwork_tracks_count,
            artwork_skipped_count=res.artwork_skipped_count,
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


def _real_device_name(mount: Path | str | None) -> Optional[str]:
    """Nombre del dispositivo mostrado en la UI:
    1. Prioridad: Etiqueta / Nombre del volumen en el SO (Finder en macOS, Explorador en Windows).
    2. Fallback: Title de la playlist maestra del iTunesCDB.
    3. Fallback: None (el caller usará el nombre genérico del modelo)."""
    if not mount:
        return None

    # 1. Nombre de volumen en el SO (Finder / Explorador)
    from cicada.ipod.device.volume_id import get_volume_label
    vol_label = get_volume_label(mount)
    if vol_label:
        return vol_label

    # 2. Fallback a Title de la playlist maestra en iTunesCDB
    cdb = Path(mount) / "iPod_Control" / "iTunes" / "iTunesCDB"
    if not cdb.is_file():
        return None
    try:
        lib = load_ipod_library(str(cdb), mount=str(mount))
    except Exception:
        return None
    if not lib:
        return None
    for pl in lib.get("mhlp", []):
        if pl.get("master_flag"):
            title = pl.get("Title")
            return title if title else None
    return None


def _ipod_to_ui(info: DeviceInfo) -> Dict[str, Any]:
    storage_data = _calculate_ipod_storage(info.mount) if info.mount else None
    generic_name = f"{info.family or 'iPod'} {info.generation or ''}".strip()
    has_consent = has_music_app_consent(info.firewire_guid) if info.firewire_guid else False
    return {
        "mount": str(info.mount),
        "ipod_name": _real_device_name(info.mount) or generic_name,
        "model_family": info.family,
        "generation": info.generation,
        "color": info.color,
        "capacity": info.capacity,
        "filesystem_type": None,
        "firewire_guid": info.firewire_guid,
        "guid_provenance": info.guid_provenance,
        "guid_is_write_safe": info.guid_is_write_safe,
        "music_app_consent_granted": has_consent,
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
    """Lista las playlists del iPod con sus pistas reales (dbid + metadata),
    resolviendo los items contra la lista de pistas. Solo lectura."""
    mount, _info = _revalidate_ipod_mount()
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    data = load_ipod_library(str(cdb), mount=str(mount))
    if data is None:
        raise HTTPException(status_code=500, detail="No se pudo leer la biblioteca del iPod.")

    tracks_by_id = {}
    for tr in data.get("mhlt", []):
        tid = tr.get("track_id")
        if tid is not None:
            tracks_by_id[tid] = tr

    playlists = []
    for p in data.get("mhlp", []):
        items = []
        for it in p.get("items", []):
            tr = tracks_by_id.get(it.get("track_id"))
            if tr is not None:
                dbid = tr.get("db_track_id")
                items.append({
                    "db_track_id": str(dbid) if dbid is not None else None,
                    "title": tr.get("Title"),
                    "artist": tr.get("Artist"),
                    "album": tr.get("Album"),
                    "length_ms": tr.get("length"),
                    "filetype": tr.get("Filetype"),
                })
        playlists.append({
            "title": p.get("Title"),
            "is_master": bool(p.get("master_flag")),
            "count": len(p.get("items", [])),
            "tracks": items,
        })
    return {"playlists": playlists, "count": len(playlists)}


@router.get("/storage", response_model=StorageInfoSchema)
def get_storage_info() -> StorageInfoSchema:
    """Obtiene el desglose de almacenamiento del iPod montado."""
    mount, _info = _revalidate_ipod_mount()
    return _calculate_ipod_storage(mount)


class PlaylistSetItem(BaseModel):
    db_track_id: Optional[str] = None
    source_path: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    filetype: Optional[str] = None


class CreatePlaylistRequest(BaseModel):
    name: str
    consent_ack: bool = False


class ImportPlaylistRequest(BaseModel):
    source_name: str
    tracks: List[PlaylistSetItem] = []
    consent_ack: bool = False


@router.post("/playlists/create", response_model=ApplyResponse)
def create_playlist(req: CreatePlaylistRequest) -> ApplyResponse:
    """Crea una nueva playlist (vacía) en el iPod."""
    if not req.name or not req.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El nombre de la playlist no puede estar vacío.", "code": "INVALID_NAME"},
        )
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        res = set_ipod_playlist(
            mount, req.name.strip(), [],
            device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "UNSAFE_DEVICE"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


@router.post("/playlists/import", response_model=ApplyResponse)
def import_playlist(req: ImportPlaylistRequest) -> ApplyResponse:
    """Importa una playlist al iPod."""
    if not req.source_name or not req.source_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El nombre de la playlist no puede estar vacío.", "code": "INVALID_NAME"},
        )
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        items = [i.dict(exclude_none=True) for i in req.tracks]
        res = set_ipod_playlist(
            mount, req.source_name.strip(), items,
            device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "UNSAFE_DEVICE"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
class DeletePlaylistRequest(BaseModel):
    playlist_name: str
    consent_ack: bool = False


@router.post("/playlists/delete", response_model=ApplyResponse)
def delete_playlist(req: DeletePlaylistRequest) -> ApplyResponse:
    """Elimina una playlist existente del iPod."""
    if not req.playlist_name or not req.playlist_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El nombre de la playlist no puede estar vacío.", "code": "INVALID_NAME"},
        )
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        res = delete_ipod_playlist(
            mount, req.playlist_name.strip(),
            device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


@router.get("/videos", response_model=VideosResponse)
def get_videos() -> VideosResponse:
    """Lista los videos (películas, series, videoclips) YA PRESENTES en el
    iPod — lista plana, sin agrupar (así la consume el frontend hoy).
    ``video_podcast`` no se incluye: ver ``/podcasts``."""
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

    lib = _load_current_library(mount)
    if not lib:
        return VideosResponse(videos=[], count=0)

    def _is_video(t: dict) -> bool:
        mt = t.get("media_type") or 0
        if (mt & MEDIA_TYPE_PODCAST) != 0 or mt == MEDIA_TYPE_VIDEO_PODCAST or t.get("podcast_flag") == 1:
            return False
        if mt == MEDIA_TYPE_AUDIOBOOK or (mt & MEDIA_TYPE_AUDIOBOOK) != 0:
            return False

        if mt in _VIDEO_MEDIA_TYPES or (mt & (MEDIA_TYPE_VIDEO | MEDIA_TYPE_MUSIC_VIDEO | MEDIA_TYPE_TV_SHOW)) != 0:
            return True
        if t.get("movie_flag") == 1 or t.get("movie_flag_2") == 1:
            return True
        ft = (t.get("filetype") or "").lower()
        loc = (t.get("Location") or t.get("path") or "").lower()
        if ft in ("m4v", "mp4", "mov") or loc.endswith((".m4v", ".mp4", ".mov")):
            return True
        return False

    videos = [
        VideoSchema(
            id=str(t.get("db_track_id") or ""),
            title=t.get("Title") or (t.get("Location") and Path(t["Location"]).stem) or "Video",
            kind=_video_kind_label(t.get("media_type")),
            duration_ms=t.get("length") or None,
            size_bytes=t.get("size") or None,
            show_name=t.get("Show") or None,
            season_number=t.get("season_number") or None,
            episode_number=t.get("episode_number") or None,
            thumb=f"/api/ipod/track/artwork?db_track_id={t.get('db_track_id')}" if t.get("db_track_id") is not None else None,
        )
        for t in lib.get("mhlt", [])
        if _is_video(t)
    ]
    return VideosResponse(videos=videos, count=len(videos))


def _resolve_ipod_track_file(mount: Path, loc: str) -> Optional[Path]:
    if not loc:
        return None
    norm = loc.replace(":", "/").replace("\\", "/").strip("/")
    cand = mount / norm
    if cand.exists():
        return cand
    parts = norm.split("/")
    if "iPod_Control" in parts:
        idx = parts.index("iPod_Control")
        cand = mount / Path(*parts[idx:])
        if cand.exists():
            return cand
    cand = mount / "iPod_Control" / norm
    if cand.exists():
        return cand
    return None


def _extract_video_frame(file_path: Path) -> Tuple[Optional[bytes], Optional[str]]:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return None, None
    try:
        cmd = [
            ffmpeg_bin, "-ss", "00:00:01", "-i", str(file_path),
            "-vframes", "1", "-q:v", "2", "-f", "image2", "-"
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=6)
        if res.returncode == 0 and res.stdout:
            return res.stdout, "image/jpeg"
        cmd[2] = "00:00:00"
        res = subprocess.run(cmd, capture_output=True, timeout=6)
        if res.returncode == 0 and res.stdout:
            return res.stdout, "image/jpeg"
    except Exception:
        pass
    return None, None


@router.get("/track/artwork")
def get_ipod_track_artwork(
    db_track_id: Optional[str] = None,
    video_id: Optional[str] = None,
    location: Optional[str] = None,
):
    target_id = db_track_id or video_id
    try:
        mount = resolve_mount()
    except Exception:
        raise HTTPException(status_code=404, detail="iPod no encontrado")

    lib = _load_current_library(mount)
    if not lib:
        raise HTTPException(status_code=404, detail="Biblioteca no disponible")

    matched_track = None
    target_int = int(target_id) if target_id and target_id.isdigit() else None

    for t in lib.get("mhlt", []):
        if target_int is not None and t.get("db_track_id") == target_int:
            matched_track = t
            break
        if target_id is not None and str(t.get("db_track_id")) == str(target_id):
            matched_track = t
            break
        if location and (t.get("Location") == location or t.get("path") == location):
            matched_track = t
            break

    if not matched_track:
        raise HTTPException(status_code=404, detail="Pista no encontrada")

    loc = matched_track.get("Location") or matched_track.get("path") or ""
    track_file = _resolve_ipod_track_file(mount, loc)
    if not track_file or not track_file.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el iPod")

    # 1. Carátula embebida en tags de audio o video
    img_bytes, mime = extract_embedded_artwork(track_file)

    # 2. Si es video y no tiene cover embebido, fotograma de video vía ffmpeg
    if not img_bytes and track_file.suffix.lower() in (".mp4", ".m4v", ".mov"):
        img_bytes, mime = _extract_video_frame(track_file)

    if not img_bytes:
        raise HTTPException(status_code=404, detail="Carátula no encontrada")

    return Response(
        content=img_bytes,
        media_type=mime or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.delete("/videos/{video_id}", response_model=ApplyResponse)
def delete_video(video_id: str, consent_ack: bool = False) -> ApplyResponse:
    """Elimina un video del iPod (base + archivo). Sin caso especial: es la
    misma pista genérica que ``POST /track/remove`` ya borra para
    cualquier media_type — este endpoint solo traduce el ``id`` de la URL."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        res = remove_track_from_ipod(mount, video_id, device_info=dev, consent_ack=consent_ack)
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(exc), "code": "TRACK_NOT_FOUND"},
        ) from exc
    except ConsentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": str(exc), "code": "CONSENT_REQUIRED"},
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


@router.get("/podcasts", response_model=PodcastsResponse)
def get_podcasts() -> PodcastsResponse:
    """Lista los podcasts YA PRESENTES en el iPod, agrupados por programa
    (Album, con fallback a Artist). Solo lectura de lo que hay en el
    dispositivo — Cicada no gestiona feeds RSS ni suscripciones (ver
    docs/VENDORED.md Paquete 8). Incluye ``video_podcast`` (cerrado en Fase
    6a) junto con podcasts de audio — son episodios del mismo programa
    conceptualmente, no pertenecen a ``/videos``."""
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

    lib = _load_current_library(mount)
    if not lib:
        return PodcastsResponse(podcasts=[], count=0)

    groups = _group_tracks_by(lib.get("mhlt", []), frozenset({MEDIA_TYPE_PODCAST, MEDIA_TYPE_VIDEO_PODCAST}))
    podcasts = [
        PodcastSchema(
            id=_slugify(name),
            name=name,
            episodes=[
                PodcastEpisodeSchema(
                    id=str(t.get("db_track_id") or ""),
                    title=t.get("Title") or "",
                    date_added=t.get("date_added") or None,
                    duration_ms=t.get("length") or None,
                    file_size=t.get("size") or None,
                )
                for t in tracks
            ],
        )
        for name, tracks in sorted(groups.items())
    ]
    return PodcastsResponse(podcasts=podcasts, count=len(podcasts))


@router.get("/audiobooks", response_model=AudiobooksResponse)
def get_audiobooks() -> AudiobooksResponse:
    """Lista los audiolibros YA PRESENTES en el iPod, agrupados por título
    (Album, con fallback a Artist). Un audiolibro puede existir de dos
    formas reales en un iTunesDB, y ambas se soportan:
      - Un solo archivo con capítulos embebidos (MHOD 17, chapter_data) —
        el camino que produce Cicada hoy (Fase 5b).
      - Varias pistas bajo el mismo Album, cada una una parte/capítulo —
        el formato que usan iTunes/iOpenPod para audiolibros multi-pista.
        Si el grupo tiene más de una pista, cada pista ES un capítulo
        (ordenadas por track_number); chapter_data embebido se ignora en
        ese caso (no debería coexistir con el split multi-pista)."""
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

    lib = _load_current_library(mount)
    if not lib:
        return AudiobooksResponse(audiobooks=[], count=0)

    groups = _group_tracks_by(lib.get("mhlt", []), MEDIA_TYPE_AUDIOBOOK)
    audiobooks = []
    for name, tracks in sorted(groups.items()):
        author = tracks[0].get("Artist") or None
        db_track_ids = [str(t.get("db_track_id")) for t in tracks if t.get("db_track_id") is not None]
        if len(tracks) > 1:
            ordered = sorted(tracks, key=lambda t: t.get("track_number") or 0)
            chapters = [
                AudiobookChapterSchema(
                    id=str(t.get("db_track_id") or ""),
                    title=t.get("Title") or "",
                    duration_ms=t.get("length") or None,
                )
                for t in ordered
            ]
        else:
            track = tracks[0]
            raw_chapters = ((track.get("chapter_data") or {}).get("chapters")) or []
            if raw_chapters:
                durations = _chapter_durations_ms(raw_chapters, track.get("length") or 0)
                chapters = [
                    AudiobookChapterSchema(
                        id=str(track.get("db_track_id") or ""),
                        title=ch.get("title") or "",
                        duration_ms=dur,
                    )
                    for ch, dur in zip(raw_chapters, durations)
                ]
            else:
                chapters = [AudiobookChapterSchema(
                    id=str(track.get("db_track_id") or ""),
                    title=track.get("Title") or "",
                    duration_ms=track.get("length") or None,
                )]
        audiobooks.append(AudiobookSchema(
            id=_slugify(name),
            title=name,
            author=author,
            chapters=chapters,
            db_track_ids=db_track_ids,
        ))

    return AudiobooksResponse(audiobooks=audiobooks, count=len(audiobooks))


class MediaTrackInput(BaseModel):
    source_path: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    length_ms: Optional[int] = None
    filetype: Optional[str] = None
    kind: Literal[
        "music", "podcast", "audiobook",
        "movie", "tv_show", "music_video", "video_podcast",
    ] = "music"
    category: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    show_name: Optional[str] = None
    podcast_enclosure_url: Optional[str] = None
    podcast_rss_url: Optional[str] = None


class MediaPlaylistInput(BaseModel):
    name: str
    source_paths: List[str] = []


class MediaSyncRequest(BaseModel):
    tracks: List[MediaTrackInput]
    consent_ack: bool = False
    keep_existing: bool = True
    playlists: List[MediaPlaylistInput] = []


@router.post("/media/sync", response_model=ApplyResponse)
def sync_media(req: MediaSyncRequest) -> ApplyResponse:
    """Copia los audios locales indicados al iPod (``iPod_Control/Music/``) y
    reescribe la base (existentes + nuevos) de forma transaccional, con backup y
    rollback. Es el 'enviar al iPod' real (a diferencia de plan/apply, que asume
    los audios ya presentes)."""
    if not req.tracks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "No se indicaron pistas.", "code": "INVALID_REQUEST"},
        )
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)

        new_tracks: List[TrackInfo] = []
        for t in req.tracks:
            src = Path(t.source_path)
            if not src.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": f"Archivo no encontrado: {t.source_path}", "code": "SOURCE_NOT_FOUND"},
                )
            ti = TrackInfo(
                title=t.title or src.stem,
                location="",
                artist=t.artist,
                album=t.album,
                album_artist=t.album_artist,
                genre=t.genre,
                year=t.year or 0,
                track_number=t.track_number or 0,
                length=t.length_ms or 0,
                filetype=(t.filetype or src.suffix.lstrip(".")).lower(),
                category=t.category,
                season_number=t.season_number or 0,
                episode_number=t.episode_number or 0,
                show_name=t.show_name,
            )
            if t.kind == "podcast":
                ti.media_type = MEDIA_TYPE_PODCAST
                ti.podcast_flag = 1
                ti.skip_when_shuffling = True
                ti.remember_position = True
                # Mismo criterio que iOpenPod (podcast_sync.py): un episodio
                # sin artist/album no es "sin autor", es el programa en sí —
                # el firmware de la app de Podcasts los usa para agrupar y
                # mostrar el episodio, así que no deben quedar vacíos.
                ti.artist = ti.artist or t.show_name
                ti.album = ti.album or t.show_name
                ti.podcast_enclosure_url = t.podcast_enclosure_url
                ti.podcast_rss_url = t.podcast_rss_url
            elif t.kind == "audiobook":
                ti.media_type = MEDIA_TYPE_AUDIOBOOK
                ti.skip_when_shuffling = True
                ti.remember_position = True
            elif t.kind == "movie":
                ti.media_type = MEDIA_TYPE_VIDEO
            elif t.kind == "tv_show":
                ti.media_type = MEDIA_TYPE_TV_SHOW
            elif t.kind == "music_video":
                ti.media_type = MEDIA_TYPE_MUSIC_VIDEO
            elif t.kind == "video_podcast":
                ti.media_type = MEDIA_TYPE_VIDEO_PODCAST
                ti.podcast_flag = 1
                ti.skip_when_shuffling = True
                ti.remember_position = True
            ti.source_path = str(src)
            new_tracks.append(ti)

        res = sync_media_to_ipod(
            mount, new_tracks, device_info=dev,
            consent_ack=req.consent_ack, keep_existing=req.keep_existing,
            playlists=[{"name": p.name, "source_paths": p.source_paths} for p in req.playlists],
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
            artwork_touched=res.artwork_touched,
            artwork_tracks_count=res.artwork_tracks_count,
            artwork_skipped_count=res.artwork_skipped_count,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": str(exc), "code": "CONSENT_REQUIRED"},
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


class PlaylistReorderRequest(BaseModel):
    playlist_name: str
    track_dbids: List[str]
    consent_ack: bool = False


@router.post("/playlist/reorder", response_model=ApplyResponse)
def reorder_playlist(req: PlaylistReorderRequest) -> ApplyResponse:
    """Reescribe una playlist existente con un nuevo orden de pistas (dbids),
    preservando el resto. Puro DB (sin copia de audio), transaccional."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        res = update_ipod_playlist(
            mount, req.playlist_name, req.track_dbids,
            device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "UNSAFE_DEVICE"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc




class PlaylistSetRequest(BaseModel):
    playlist_name: str
    items: List[PlaylistSetItem]
    consent_ack: bool = False


@router.post("/playlist/set", response_model=ApplyResponse)
def set_playlist(req: PlaylistSetRequest) -> ApplyResponse:
    """Reescribe (o crea) una playlist con el contenido ordenado ``items`` (mezcla
    de pistas ya en el iPod y nuevas de la biblioteca, que se copian). Preserva el
    resto. Generaliza reordenar + agregar. Transaccional."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        items = [i.dict(exclude_none=True) for i in req.items]
        res = set_ipod_playlist(
            mount, req.playlist_name, items,
            device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "UNSAFE_DEVICE"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class TrackRemoveRequest(BaseModel):
    db_track_id: str
    consent_ack: bool = False


@router.post("/track/remove", response_model=ApplyResponse)
def remove_track(req: TrackRemoveRequest) -> ApplyResponse:
    """Elimina una pista del iPod (base + audio), quitándola también de cualquier
    playlist que la referenciaba. Preserva el resto. Transaccional."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        res = remove_track_from_ipod(
            mount, req.db_track_id, device_info=dev, consent_ack=req.consent_ack,
        )
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "INVALID_REQUEST"}) from exc
    except UnsafeDeviceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "UNSAFE_DEVICE"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class PlaybackSyncResponse(BaseModel):
    guid: str
    total_tracks_scanned: int
    tracks_changed: int
    total_delta_plays: int
    total_delta_skips: int
    ratings_updated_count: int


@router.post("/sync/playback", response_model=PlaybackSyncResponse)
def sync_playback(dry_run: bool = False) -> PlaybackSyncResponse:
    """Escanea los contadores de reproducción/rating del iPod y actualiza la
    línea base local (~/.cicada/ipod.db). Solo lee el dispositivo y escribe en
    SQLite local — nunca escribe en el iPod, no requiere consentimiento.

    ``dry_run=true`` calcula el informe sin persistir la nueva línea base
    (útil para previsualizar antes de confirmar)."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        if not dev.firewire_guid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "No se pudo identificar el GUID del iPod.", "code": "NO_GUID"},
            )
        if dry_run:
            from cicada.ipod.sync.bidirectional import compute_playback_deltas
            report = compute_playback_deltas(mount, SyncStateDB(), dev.firewire_guid)
        else:
            report = sync_playback_stats(mount, dev)
        return PlaybackSyncResponse(
            guid=report.guid,
            total_tracks_scanned=report.total_tracks_scanned,
            tracks_changed=len(report.tracks_with_deltas),
            total_delta_plays=report.total_delta_plays,
            total_delta_skips=report.total_delta_skips,
            ratings_updated_count=report.ratings_updated_count,
        )
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class TrackRateRequest(BaseModel):
    db_track_id: str
    rating: int


@router.post("/track/rate", response_model=ApplyResponse)
def rate_track_locally(req: TrackRateRequest) -> ApplyResponse:
    """Asigna un rating desde Cicada, independiente del iPod (local_playback_state).
    Solo escribe SQLite local — nunca el iPod, no requiere consentimiento. Es el
    'lado local' que hace posible detectar conflictos de verdad más adelante."""
    if not (0 <= req.rating <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "rating debe estar entre 0 y 100.", "code": "INVALID_REQUEST"})
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        if not dev.firewire_guid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail={"error": "No se pudo identificar el GUID del iPod.", "code": "NO_GUID"})
        sync_db = SyncStateDB()
        sync_db.upsert_device(DeviceRecord(
            guid=dev.firewire_guid, family_id=dev.family_id,
            model_num=dev.model_number, serial=dev.serial,
            name=f"{dev.family or ''} {dev.generation or ''}".strip() or None,
        ))
        sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(
            guid=dev.firewire_guid, ipod_dbid=int(req.db_track_id), local_rating=req.rating,
        ))
        return ApplyResponse(success=True, tracks_written=1)
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class RatingConflictSchema(BaseModel):
    ipod_dbid: str
    title: Optional[str] = None
    artist: Optional[str] = None
    known_rating: int
    local_rating: int
    device_rating: int


class ConflictsListResponse(BaseModel):
    conflicts: List[RatingConflictSchema] = []
    count: int = 0


def _conflict_track_titles(mount: Path) -> Dict[int, tuple]:
    """{dbid: (title, artist)} para enriquecer la lista de conflictos."""
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    if not cdb.is_file():
        return {}
    lib = load_ipod_library(str(cdb), mount=str(mount))
    if not lib:
        return {}
    return {
        t.get("db_track_id"): (t.get("Title"), t.get("Artist"))
        for t in lib.get("mhlt", []) if t.get("db_track_id") is not None
    }


def _scan_conflicts(mount: Path, dev: DeviceInfo) -> tuple:
    """(sync_db, guid, conflicts): helper compartido por los 3 endpoints de conflictos."""
    if not dev.firewire_guid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "No se pudo identificar el GUID del iPod.", "code": "NO_GUID"})
    sync_db = SyncStateDB()
    result = scan_for_conflicts(mount, sync_db, dev.firewire_guid)
    return sync_db, dev.firewire_guid, result.conflicts


@router.get("/conflicts", response_model=ConflictsListResponse)
def list_conflicts() -> ConflictsListResponse:
    """Escanea conflictos de rating pendientes (local vs. dispositivo vs.
    baseline). Solo lectura — nunca resuelve nada aquí."""
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        _sync_db, _guid, conflicts = _scan_conflicts(mount, dev)
        titles = _conflict_track_titles(mount) if conflicts else {}
        schemas = [
            RatingConflictSchema(
                ipod_dbid=str(c.ipod_dbid),
                title=(titles.get(c.ipod_dbid) or (None, None))[0],
                artist=(titles.get(c.ipod_dbid) or (None, None))[1],
                known_rating=c.known_rating, local_rating=c.local_rating,
                device_rating=c.device_rating,
            )
            for c in conflicts
        ]
        return ConflictsListResponse(conflicts=schemas, count=len(schemas))
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class ConflictResolveRequest(BaseModel):
    ipod_dbid: str
    resolution: str
    consent_ack: bool = False


@router.post("/conflicts/resolve", response_model=ApplyResponse)
def resolve_one_conflict(req: ConflictResolveRequest) -> ApplyResponse:
    """Resuelve UN conflicto pendiente. 'local' escribe el rating local al
    iPod (requiere consentimiento si es la primera escritura); 'device' solo
    alinea las tablas locales al valor que el iPod ya tiene."""
    if req.resolution not in ("local", "device"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "resolution debe ser 'local' o 'device'.", "code": "INVALID_REQUEST"})
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        sync_db, _guid, conflicts = _scan_conflicts(mount, dev)
        target_dbid = int(req.ipod_dbid)
        matching = [c for c in conflicts if c.ipod_dbid == target_dbid]
        if not matching:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail={"error": f"No hay conflicto pendiente para la pista {target_dbid}.",
                                        "code": "CONFLICT_NOT_FOUND"})
        res = resolve_conflicts(mount, sync_db, matching, req.resolution,
                                device_info=dev, consent_ack=req.consent_ack)
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc


class ConflictResolveAllRequest(BaseModel):
    resolution: str
    consent_ack: bool = False


@router.post("/conflicts/resolve-all", response_model=ApplyResponse)
def resolve_all_conflicts(req: ConflictResolveAllRequest) -> ApplyResponse:
    """Aplica la MISMA política a todos los conflictos pendientes, en una
    sola escritura por lote si resolution='local' (no una por pista)."""
    if req.resolution not in ("local", "device"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": "resolution debe ser 'local' o 'device'.", "code": "INVALID_REQUEST"})
    try:
        mount = resolve_mount()
        dev = read_device_info(mount)
        sync_db, _guid, conflicts = _scan_conflicts(mount, dev)
        res = resolve_conflicts(mount, sync_db, conflicts, req.resolution,
                                device_info=dev, consent_ack=req.consent_ack)
        return ApplyResponse(
            success=res.success,
            backup_path=str(res.backup_path) if res.backup_path else None,
            restored_from_backup=res.restored_from_backup,
            first_write_committed=res.first_write_committed,
            tracks_written=res.tracks_written,
            error=res.error,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(exc), "code": "CONSENT_REQUIRED"}) from exc
    except MountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": str(exc), "code": "MOUNT_NOT_FOUND"}) from exc
    except WriteGuardError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(exc), "code": "WRITE_GUARD_ERROR"}) from exc
