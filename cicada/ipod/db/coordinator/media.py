"""Copia de audio de la biblioteca local al iPod — prerequisito de la escritura
de base. plan/apply solo escriben la base de datos asumiendo que los audios ya
están en el iPod; este módulo copia los archivos a ``iPod_Control/Music/Fxx/``,
les asigna una ``location`` estilo iTunes, y coordina la limpieza en rollback.
Solo AÑADE archivos con nombres únicos: nunca sobrescribe audio existente."""
from __future__ import annotations

import logging
import os
import random
import shutil
import string
from dataclasses import dataclass
from pathlib import Path

from cicada.ipod.device import durability
from cicada.ipod.device.safe_write import guarded_durable_unlink
from cicada.ipod.device.write_guard import assert_within_ipod_control, assert_writable

logger = logging.getLogger(__name__)

__all__ = [
    "MediaAssignment",
    "existing_music_names",
    "assign_location",
    "assign_media_locations",
    "copy_media",
    "cleanup_media",
    "sync_media_to_ipod",
    "update_ipod_playlist",
    "set_ipod_playlist",
    "remove_track_from_ipod",
    "preserve_existing_playlists",
    "push_ratings_to_ipod",
]

_MUSIC_BUCKETS = 50
_NAME_CHARS = string.ascii_uppercase
_NAME_LEN = 4


@dataclass
class MediaAssignment:
    source: Path
    ipod_location: str
    dest_relpath: str


def existing_music_names(mount: str | Path) -> set[str]:
    """Nombres de archivo ya presentes bajo ``iPod_Control/Music/`` (para evitar
    colisiones al asignar nombres nuevos)."""
    music = Path(mount) / "iPod_Control" / "Music"
    names: set[str] = set()
    if music.is_dir():
        for bucket in music.iterdir():
            if bucket.is_dir():
                for f in bucket.iterdir():
                    if f.is_file():
                        names.add(f.name)
    return names


def assign_location(ext: str, taken: set[str], *, rng: random.Random | None = None) -> tuple[str, str]:
    """Devuelve ``(ipod_location, dest_relpath)`` con un nombre único. Muta ``taken``."""
    r = rng or random
    ext = ("." + ext.lstrip(".")).lower() if ext else ""
    bucket = f"F{r.randrange(_MUSIC_BUCKETS):02d}"
    while True:
        fname = "".join(r.choice(_NAME_CHARS) for _ in range(_NAME_LEN)) + ext
        if fname not in taken:
            break
    taken.add(fname)
    return (
        f":iPod_Control:Music:{bucket}:{fname}",
        f"iPod_Control/Music/{bucket}/{fname}",
    )


def assign_media_locations(
    mount: str | Path,
    sources: list[str | Path],
    *,
    rng: random.Random | None = None,
) -> list[MediaAssignment]:
    """Asigna una ``location`` única a cada archivo de audio local (no copia nada)."""
    taken = existing_music_names(mount)
    out: list[MediaAssignment] = []
    for src in sources:
        src = Path(src)
        loc, rel = assign_location(src.suffix, taken, rng=rng)
        out.append(MediaAssignment(source=src, ipod_location=loc, dest_relpath=rel))
    return out


def _copy_into_ipod(source: Path, dest: Path, mount: Path) -> None:
    """Copia ``source`` (archivo local) a ``dest`` (nuevo, en el iPod) sin
    sobrescribir (``O_EXCL``), con fsync de archivo y directorio. **Preserva el
    source** (a diferencia de ``durable_publish_new``, que borra su origen temp)."""
    assert_within_ipod_control(dest, mount)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as df:
            with open(source, "rb") as sf:
                shutil.copyfileobj(sf, df)
            df.flush()
            os.fsync(df.fileno())
    except BaseException:
        try:
            os.unlink(str(dest))
        except OSError:
            pass
        raise
    durability.flush_parent_directory(dest)


def copy_media(mount: str | Path, assignments: list[MediaAssignment]) -> list[str]:
    """Copia cada ``source`` a su destino en el iPod (confinado + durable). Devuelve
    las ``dest_relpath`` copiadas, para poder limpiarlas en rollback. Si alguna
    copia falla, borra lo ya copiado y relanza."""
    mount = Path(mount)
    assert_writable(mount)
    copied: list[str] = []
    try:
        for a in assignments:
            _copy_into_ipod(Path(a.source), mount / a.dest_relpath, mount)
            copied.append(a.dest_relpath)
    except BaseException:
        cleanup_media(mount, copied)
        raise
    return copied


def cleanup_media(mount: str | Path, relpaths: list[str]) -> None:
    """Borra (confinado) los audios copiados. Best-effort: no lanza."""
    mount = Path(mount)
    for rel in relpaths:
        try:
            guarded_durable_unlink(mount / rel, mount, missing_ok=True)
        except Exception:
            pass


def _read_audio_info(path: str | Path) -> tuple[int, int, int, bool]:
    """(length_ms, bitrate_kbps, sample_rate_hz, vbr) leídos del archivo con mutagen.
    El archivo es la fuente autoritativa de estos campos técnicos: sin ``length``
    correcto, el iPod no puede buscar dentro de la pista. Devuelve ceros si falla."""
    try:
        import mutagen
        f = mutagen.File(str(path))
        info = getattr(f, "info", None) if f is not None else None
        if info is None:
            return 0, 0, 0, False
        length_ms = int(round(float(getattr(info, "length", 0) or 0) * 1000))
        bitrate = int(getattr(info, "bitrate", 0) or 0) // 1000
        sample_rate = int(getattr(info, "sample_rate", 0) or 0)
        mode = getattr(info, "bitrate_mode", None)
        vbr = mode is not None and str(mode).rsplit(".", 1)[-1] in ("VBR", "ABR")
        return length_ms, bitrate, sample_rate, vbr
    except Exception:
        return 0, 0, 0, False


def _norm_name(s) -> str:
    return str(s or "").strip().lower()


def _heal_track_lengths(mount, tracks) -> None:
    """Rellena ``length=0`` de pistas existentes leyendo su audio del iPod (para
    poder buscar dentro de ellas). Las de iOpenPod ya traen length>0 y no se tocan."""
    mount = Path(mount)
    for ti in tracks:
        if not ti.length and ti.location:
            fp = mount / ti.location.lstrip(":").replace(":", "/")
            if fp.is_file():
                lms, br, sr, vbr = _read_audio_info(fp)
                if lms:
                    ti.length = lms
                if br and not ti.bitrate:
                    ti.bitrate = br
                if sr and not ti.sample_rate:
                    ti.sample_rate = sr
                if vbr:
                    ti.vbr = vbr


def _prepare_new_tracks(mount, new_tracks):
    """Asigna location + tamaño + info de audio + dbid a pistas nuevas (con
    ``source_path``). Devuelve (assignments, {source_path: dbid})."""
    assignments = assign_media_locations(mount, [ti.source_path for ti in new_tracks])
    for ti, a in zip(new_tracks, assignments):
        ti.location = a.ipod_location
        if not ti.size:
            try:
                ti.size = Path(ti.source_path).stat().st_size
            except OSError:
                pass
        lms, br, sr, vbr = _read_audio_info(ti.source_path)
        if lms:
            ti.length = lms
        if br:
            ti.bitrate = br
        if sr:
            ti.sample_rate = sr
        ti.vbr = vbr
        if not ti.chapter_data:
            from cicada.ipod.db.writer.chapter_extraction import extract_chapters
            chapters = extract_chapters(str(ti.source_path))
            if chapters:
                ti.chapter_data = {"chapters": chapters}
        if not ti.db_track_id:
            ti.db_track_id = random.getrandbits(64)
    return assignments, {str(ti.source_path): ti.db_track_id for ti in new_tracks}


def _trackid_to_dbid(lib) -> dict:
    """Mapa track_id (índice pequeño) -> db_track_id (persistente). Los items de
    playlist referencian por ``track_id``, no por el dbid."""
    m = {}
    for t in lib.get("mhlt", []):
        tid, dbid = t.get("track_id"), t.get("db_track_id")
        if tid is not None and dbid is not None:
            m[tid] = dbid
    return m


def _playlist_dbids(pl, tid2db) -> list:
    """Resuelve los items de una playlist a dbids (vía track_id; fallback a los
    persistent_id del item)."""
    out = []
    for it in pl.get("items", []):
        tid = it.get("track_id")
        dbid = tid2db.get(tid) if tid is not None else None
        if not dbid:
            dbid = it.get("track_persistent_id") or it.get("db_track_id")
        if dbid:
            out.append(dbid)
    return out


def update_ipod_playlist(mount, playlist_name, ordered_dbids, *, device_info, consent_ack=False):
    """Reescribe UNA playlist existente con un nuevo orden de pistas (dbids),
    preservando todo lo demás (pistas + resto de playlists). Puro DB, sin copia de
    audio. Transaccional vía apply (backup + rollback). Devuelve el ApplyResult."""
    from cicada.ipod.db.coordinator.apply import apply
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.models import PlaylistInfo
    from cicada.ipod.db.parser import load_ipod_library
    from cicada.ipod.db.writer._track_conversion import track_dict_to_info

    mount = Path(mount)
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None
    if not lib:
        raise ValueError("No se pudo leer la biblioteca del iPod.")

    tracks = [track_dict_to_info(t) for t in lib.get("mhlt", [])]
    _heal_track_lengths(mount, tracks)
    existing_dbids = {ti.db_track_id for ti in tracks}
    ordered = [int(d) for d in ordered_dbids if int(d) in existing_dbids]

    tid2db = _trackid_to_dbid(lib)
    want = _norm_name(playlist_name)
    regular, found = [], False
    for pl in lib.get("mhlp", []):
        if pl.get("master_flag"):
            continue
        if not found and _norm_name(pl.get("Title")) == want:
            regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist", track_ids=ordered, master=False))
            found = True
        else:
            regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist",
                                        track_ids=_playlist_dbids(pl, tid2db), master=False))
    if not found:
        raise ValueError(f"Playlist '{playlist_name}' no encontrada en el iPod.")

    try:
        from cicada.ipod.sync.playlists import extract_smart_playlists_for_preservation
        smart = extract_smart_playlists_for_preservation(mount) or []
    except Exception:
        smart = []

    plan = create_plan(
        mount, tracks, device_info=device_info,
        playlists=regular or None, smart_playlists=smart or None,
    )
    if plan.consent_needed and not consent_ack:
        raise ConsentRequiredError(
            "Se requiere aceptar la advertencia de Music.app antes de escribir."
        )
    return apply(plan, mount=mount, device_info=device_info, consent_ack=consent_ack)


def set_ipod_playlist(mount, playlist_name, items, *, device_info, consent_ack=False):
    """Reescribe (o crea) una playlist con ``items`` ordenados: cada uno
    ``{"db_track_id": int}`` (ya en el iPod) o ``{"source_path": str, "title", ...}``
    (nuevo de la biblioteca: se copia su audio). Preserva el resto. Transaccional;
    limpia los audios nuevos si falla. Generaliza reordenar + agregar."""
    from cicada.ipod.db.coordinator.apply import apply
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.models import PlaylistInfo, TrackInfo
    from cicada.ipod.db.parser import load_ipod_library
    from cicada.ipod.db.writer._track_conversion import track_dict_to_info

    mount = Path(mount)
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None
    if not lib:
        raise ValueError("No se pudo leer la biblioteca del iPod.")

    existing_tracks = [track_dict_to_info(t) for t in lib.get("mhlt", [])]
    _heal_track_lengths(mount, existing_tracks)
    existing_dbids = {ti.db_track_id for ti in existing_tracks}

    new_by_src = {}
    for it in items:
        sp = it.get("source_path")
        if sp and it.get("db_track_id") is None and str(sp) not in new_by_src:
            sp = str(sp)
            ti = TrackInfo(
                title=it.get("title") or Path(sp).stem, location="",
                artist=it.get("artist"), album=it.get("album"),
                filetype=(it.get("filetype") or Path(sp).suffix.lstrip(".")).lower(),
            )
            ti.source_path = sp
            new_by_src[sp] = ti
    new_tracks = list(new_by_src.values())
    assignments, src_to_dbid = _prepare_new_tracks(mount, new_tracks) if new_tracks else ([], {})

    ordered = []
    for it in items:
        dbid = it.get("db_track_id")
        if dbid is not None and int(dbid) in existing_dbids:
            ordered.append(int(dbid))
        elif it.get("source_path") and str(it["source_path"]) in src_to_dbid:
            ordered.append(src_to_dbid[str(it["source_path"])])

    full_tracks = existing_tracks + new_tracks

    tid2db = _trackid_to_dbid(lib)
    want = _norm_name(playlist_name)
    regular, found = [], False
    for pl in lib.get("mhlp", []):
        if pl.get("master_flag"):
            continue
        if not found and _norm_name(pl.get("Title")) == want:
            regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist", track_ids=ordered, master=False))
            found = True
        else:
            regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist",
                                        track_ids=_playlist_dbids(pl, tid2db), master=False))
    if not found:
        regular.append(PlaylistInfo(name=playlist_name, track_ids=ordered, master=False))

    try:
        from cicada.ipod.sync.playlists import extract_smart_playlists_for_preservation
        smart = extract_smart_playlists_for_preservation(mount) or []
    except Exception:
        smart = []

    plan = create_plan(
        mount, full_tracks, device_info=device_info,
        playlists=regular or None, smart_playlists=smart or None,
    )
    if plan.consent_needed and not consent_ack:
        raise ConsentRequiredError(
            "Se requiere aceptar la advertencia de Music.app antes de escribir."
        )

    copied = copy_media(mount, assignments) if assignments else []
    try:
        result = apply(plan, mount=mount, device_info=device_info, consent_ack=consent_ack)
    except BaseException:
        cleanup_media(mount, copied)
        raise
    if not result.success:
        cleanup_media(mount, copied)
    return result


def remove_track_from_ipod(mount, db_track_id, *, device_info, consent_ack=False):
    """Elimina UNA pista del iPod: la quita de la base (y de cualquier playlist que
    la referenciaba) y borra su archivo de audio. Transaccional vía ``apply``; el
    audio solo se borra **después** de un ``apply`` exitoso (si falla, nada cambia
    en disco)."""
    from cicada.ipod.db.coordinator.apply import apply
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.models import PlaylistInfo
    from cicada.ipod.db.parser import load_ipod_library
    from cicada.ipod.db.writer._track_conversion import track_dict_to_info

    mount = Path(mount)
    db_track_id = int(db_track_id)
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None
    if not lib:
        raise ValueError("No se pudo leer la biblioteca del iPod.")

    target = next((t for t in lib.get("mhlt", []) if t.get("db_track_id") == db_track_id), None)
    if target is None:
        raise ValueError(f"Pista {db_track_id} no encontrada en el iPod.")
    location = target.get("Location") or target.get("location")

    tracks = [track_dict_to_info(t) for t in lib.get("mhlt", []) if t.get("db_track_id") != db_track_id]
    _heal_track_lengths(mount, tracks)

    tid2db = _trackid_to_dbid(lib)
    regular = []
    for pl in lib.get("mhlp", []):
        if pl.get("master_flag"):
            continue
        tids = [d for d in _playlist_dbids(pl, tid2db) if d != db_track_id]
        regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist", track_ids=tids, master=False))

    try:
        from cicada.ipod.sync.playlists import extract_smart_playlists_for_preservation
        smart = extract_smart_playlists_for_preservation(mount) or []
    except Exception:
        smart = []

    plan = create_plan(
        mount, tracks, device_info=device_info,
        playlists=regular or None, smart_playlists=smart or None,
    )
    if plan.consent_needed and not consent_ack:
        raise ConsentRequiredError(
            "Se requiere aceptar la advertencia de Music.app antes de escribir."
        )

    result = apply(plan, mount=mount, device_info=device_info, consent_ack=consent_ack)
    if result.success and location:
        relpath = str(location).lstrip(":").replace(":", "/")
        try:
            guarded_durable_unlink(mount / relpath, mount, missing_ok=True)
        except Exception:
            logger.warning("No se pudo borrar el audio %r tras eliminar la pista %d.", relpath, db_track_id)
    return result


def push_ratings_to_ipod(mount, ratings: dict, *, device_info, consent_ack=False):
    """Escribe rating(s) en el iPod para los dbids dados — reescritura completa
    de la base (como toda escritura en este módulo), preservando playlists.
    ``ratings``: ``{db_track_id: rating_0_a_100}``. dbids que no existen en el
    iPod se ignoran (pudo borrarse la pista entre el escaneo y la resolución);
    si NINGUNO existe, no tiene sentido escribir — se lanza ``ValueError``.
    Usado tanto por la resolución individual de un conflicto ("local gana")
    como por el push silencioso de cambios solo-locales (ambos casos son la
    misma operación: hacer que el dispositivo refleje el rating local)."""
    from cicada.ipod.db.coordinator.apply import apply
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.parser import load_ipod_library
    from cicada.ipod.db.writer._track_conversion import track_dict_to_info

    mount = Path(mount)
    ratings = {int(k): int(v) for k, v in ratings.items()}
    cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None
    if not lib:
        raise ValueError("No se pudo leer la biblioteca del iPod.")

    found = {t.get("db_track_id") for t in lib.get("mhlt", [])} & ratings.keys()
    if not found:
        raise ValueError("Ninguna de las pistas indicadas existe en el iPod.")

    tracks = []
    for t in lib.get("mhlt", []):
        ti = track_dict_to_info(t)
        if ti.db_track_id in ratings:
            ti.rating = ratings[ti.db_track_id]
        tracks.append(ti)
    _heal_track_lengths(mount, tracks)

    regular, smart = preserve_existing_playlists(mount, lib)

    plan = create_plan(
        mount, tracks, device_info=device_info,
        playlists=regular or None, smart_playlists=smart or None,
    )
    if plan.consent_needed and not consent_ack:
        raise ConsentRequiredError(
            "Se requiere aceptar la advertencia de Music.app antes de escribir."
        )
    return apply(plan, mount=mount, device_info=device_info, consent_ack=consent_ack)


def preserve_existing_playlists(mount, lib=None):
    """(regulares, smart) como ``PlaylistInfo``, listas para pasar a ``create_plan()``
    y así no perder las playlists que el iPod ya tiene. **Toda escritura completa de
    la base debe llamar esto** — si ``create_plan`` recibe ``playlists=None``, el
    writer solo crea la master y descarta las demás. ``lib`` opcional evita
    re-parsear si ya se leyó (p.ej. en ``_build_playlists``)."""
    from cicada.ipod.db.models import PlaylistInfo
    from cicada.ipod.db.parser import load_ipod_library

    mount = Path(mount)
    if lib is None:
        cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
        lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None

    regular = []
    if lib:
        tid2db = _trackid_to_dbid(lib)
        for pl in lib.get("mhlp", []):
            if pl.get("master_flag"):
                continue
            regular.append(PlaylistInfo(name=pl.get("Title") or "Playlist",
                                        track_ids=_playlist_dbids(pl, tid2db), master=False))
    try:
        from cicada.ipod.sync.playlists import extract_smart_playlists_for_preservation
        smart = extract_smart_playlists_for_preservation(mount) or []
    except Exception:
        smart = []
    return regular, smart


def _build_playlists(mount, lib, sent_playlists, src_to_dbid):
    """(regulares, smart) como ``PlaylistInfo`` para create_plan: **preserva** las
    playlists existentes del iPod (imprescindible — si no, cada sync las borraría) y
    añade las **enviadas** (``{"name", "source_paths"}``) referenciando los dbid de
    las pistas nuevas."""
    from cicada.ipod.db.models import PlaylistInfo
    regular, smart = preserve_existing_playlists(mount, lib)
    regular = list(regular)
    for np in (sent_playlists or []):
        paths = np.get("source_paths", [])
        tids = [src_to_dbid[str(sp)] for sp in paths if str(sp) in src_to_dbid]
        if len(tids) < len(paths):
            logger.warning(
                "Playlist enviada %r: %d de %d pistas no se pudieron resolver a un dbid "
                "(quedaron fuera del envío); se crea igualmente con las que sí resolvieron.",
                np.get("name"), len(paths) - len(tids), len(paths),
            )
        regular.append(PlaylistInfo(name=np.get("name") or "Playlist", track_ids=tids, master=False))
    return regular, smart


def _existing_master_playlist_name(lib) -> str | None:
    """``Title`` de la playlist maestra actual del dispositivo, si existe.

    El "nombre del iPod" que el usuario ve/edita en Finder/Música/iTunes
    ES este campo — no hay un registro de identidad separado en el
    dispositivo (confirmado contra iOpenPod: su función de renombrar el
    iPod solo reescribe este ``Title``). ``lib`` ya viene parseado por el
    caller (preservación de tracks existentes), sin lectura extra."""
    if not lib:
        return None
    for pl in lib.get("mhlp", []):
        if pl.get("master_flag"):
            title = pl.get("Title")
            return title if title else None
    return None


def sync_media_to_ipod(
    mount: str | Path,
    new_tracks,
    *,
    device_info,
    consent_ack: bool = False,
    keep_existing: bool = True,
    master_playlist_name: str | None = None,
    playlists=None,
):
    """Copia el audio de ``new_tracks`` (cada uno con ``source_path`` local) al iPod
    y reescribe la base (existentes + nuevos) de forma transaccional.

    ``playlists``: lista opcional de ``{"name", "source_paths"}`` a **crear** en el
    iPod. Las playlists existentes se **preservan** siempre (round-trip).

    ``master_playlist_name``: si es ``None`` (caso normal — hoy no hay UI de
    rename), se preserva el nombre que el dispositivo ya tenía puesto (leído
    del ``Title`` de la playlist maestra existente, sin costo extra: ya se
    parsea el ``iTunesCDB`` para preservar tracks). Sin eso, cada sync pisaba
    en silencio un nombre real (p. ej. "iPod de Juan", puesto por el usuario
    en Finder/Música) con el genérico "iPod" — pérdida de datos activa.
    Si el dispositivo nunca tuvo una playlist maestra (primera sync), o el
    caller pasa un nombre explícito, se usa ese valor.

    Orden: asigna locations → ``create_plan`` (valida seguridad; no copia si falla)
    → copia audio → ``apply`` (instala la base con su backup+rollback). En cualquier
    fallo, ``apply`` restaura la base y aquí se borran los audios nuevos. ``apply``
    queda intacto (sin riesgo de regresión). Devuelve el ``ApplyResult`` de apply.
    """
    from cicada.ipod.db.coordinator.apply import apply
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.parser import load_ipod_library
    from cicada.ipod.db.writer._track_conversion import track_dict_to_info

    mount = Path(mount)
    new_tracks = list(new_tracks)
    for ti in new_tracks:
        if not getattr(ti, "source_path", None):
            raise ValueError("cada track nuevo requiere source_path (archivo local)")

    assignments, src_to_dbid = _prepare_new_tracks(mount, new_tracks)

    existing = []
    lib = None
    if keep_existing:
        cdb = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
        lib = load_ipod_library(str(cdb), mount=str(mount)) if cdb.is_file() else None
        if lib:
            existing = [track_dict_to_info(t) for t in lib.get("mhlt", [])]
            _heal_track_lengths(mount, existing)
    full = existing + new_tracks

    if master_playlist_name is None:
        from cicada.ipod.device.volume_id import get_volume_label
        master_playlist_name = get_volume_label(mount) or _existing_master_playlist_name(lib) or "iPod"

    reg_playlists, smart_playlists = _build_playlists(mount, lib, playlists, src_to_dbid)

    plan = create_plan(
        mount, full, device_info=device_info,
        master_playlist_name=master_playlist_name,
        playlists=reg_playlists or None,
        smart_playlists=smart_playlists or None,
    )
    if plan.consent_needed and not consent_ack:
        raise ConsentRequiredError(
            "Se requiere aceptar la advertencia de Music.app antes de la primera escritura."
        )

    copied = copy_media(mount, assignments)
    try:
        result = apply(plan, mount=mount, device_info=device_info, consent_ack=consent_ack)
    except BaseException:
        cleanup_media(mount, copied)
        raise
    if not result.success:
        cleanup_media(mount, copied)
    return result
