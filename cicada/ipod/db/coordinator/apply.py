"""Orquestador de aplicación de planes con rollback transaccional — Etapa 2c.

Implementa la instalación atómica de los 7 artefactos de base de datos en el iPod
(más ArtworkDB + 4 .ithmb cuando el plan tocó artwork — Fase 4, Etapa 4d, ver
:data:`Plan.artwork_touched`) mediante 5 fases rigurosas:

- **Fase A (Precondiciones)**: Revalida montaje, permisos de escritura, procedencia
  del GUID, gate de consentimiento, integridad de artefactos en staging y coincidencia
  de la huella pre-estado (:class:`PreStateFingerprint`). Falla -> dispositivo intacto.
- **Fase B (Backup verificado)**: Crea snapshot `DB_ONLY` con :func:`create_backup`
  (incluye `iPod_Control/Artwork/` solo si `plan.artwork_touched`) y re-verifica su
  integridad criptográfica antes de cualquier mutación. Falla -> dispositivo intacto.
- **Fase C (Stage en device)**: Transfiere los archivos a `<destino>.cicada-new` en el
  mismo directorio del iPod y ejecuta fsync sobre cada uno. Todo el I/O pesado ocurre aquí.
  Falla -> se purgan los `.cicada-new`; destinos intactos.
- **Fase D (Commit por renames)**: Escribe atómicamente el marcador `inflight.json` en
  almacenamiento local y ejecuta `os.replace` en orden canónico estricto: primero
  ArtworkDB/.ithmb si aplica (lo que referencian debe existir antes que quien referencia),
  luego `Locations.itdb` -> `Locations.itdb.cbk` -> `Library.itdb` -> `Dynamic.itdb` ->
  `Extras.itdb` -> `Genius.itdb` -> `iTunesCDB` (el ancla final).
  Falla -> rollback inmediato con :func:`restore_backup`.
- **Fase E (Verificación post-commit)**: Re-lee el iPod (parser iTunesCDB + sqlite3 +
  ArtworkDB si aplica), valida firma HASHAB, conteo de tracks, consistencia e
  integridad referencial artwork_id_ref -> ArtworkDB. Falla -> rollback inmediato.
  Éxito -> elimina `inflight.json`, marca primera escritura en consentimiento y retorna éxito.

Incluye :func:`recover_inflight_commit` para recuperación cross-sesión si un corte de
energía interrumpe un commit en progreso.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from cicada.ipod.db.artwork.chunks import read_artworkdb
from cicada.ipod.db.coordinator.consent import (
    ConsentRequiredError,
    _guid_hash,
    mark_first_write_committed,
    record_music_app_consent,
)
from cicada.ipod.db.coordinator.plan import (
    DATABASE_TARGET_RELPATHS,
    InconsistentArtifactsError,
    Plan,
    UnsafeDeviceError,
    artwork_target_relpaths,
)
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.sqlite._helpers import u64
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.backup import (
    BackupMode,
    create_backup,
    restore_backup,
)
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo
from cicada.ipod.device.durability import flush_written_file
from cicada.ipod.paths import cicada_home
from cicada.ipod.device.write_guard import (
    assert_within_ipod_control,
    assert_writable,
    resolve_mount,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ApplyResult",
    "ApplyError",
    "StalePlanError",
    "PostCommitVerifyError",
    "apply",
    "default_commit_dir",
    "get_inflight_path",
    "set_inflight_marker",
    "clear_inflight_marker",
    "get_inflight_marker",
    "recover_inflight_commit",
    "purge_staging_temps",
]

_BASE_INSTALL_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("iTunes Library.itlp/Locations.itdb", "iPod_Control/iTunes/iTunes Library.itlp/Locations.itdb"),
    ("iTunes Library.itlp/Locations.itdb.cbk", "iPod_Control/iTunes/iTunes Library.itlp/Locations.itdb.cbk"),
    ("iTunes Library.itlp/Library.itdb", "iPod_Control/iTunes/iTunes Library.itlp/Library.itdb"),
    ("iTunes Library.itlp/Dynamic.itdb", "iPod_Control/iTunes/iTunes Library.itlp/Dynamic.itdb"),
    ("iTunes Library.itlp/Extras.itdb", "iPod_Control/iTunes/iTunes Library.itlp/Extras.itdb"),
    ("iTunes Library.itlp/Genius.itdb", "iPod_Control/iTunes/iTunes Library.itlp/Genius.itdb"),
    ("iTunesCDB", "iPod_Control/iTunes/iTunesCDB"),
)

def _artwork_install_sequence(plan: Plan) -> tuple[tuple[str, str], ...]:
    """ArtworkDB + un .ithmb por formato DEL DISPOSITIVO de este plan (Fase 4,
    Etapas 4d/4f-1) — se instalan ANTES de la secuencia base para que, cuando
    iTunesCDB/Library.itdb (que referencian artwork_id_ref) se vuelvan
    visibles, el ArtworkDB que referencian ya exista en disco. Vacío si el
    plan no tocó artwork."""
    if not plan.artwork_touched:
        return ()
    formats = plan.capabilities.cover_art_formats if plan.capabilities else ()
    relpaths = artwork_target_relpaths(formats)
    return tuple((f"Artwork/{rel.rsplit('/', 1)[-1]}", rel) for rel in relpaths)


def _install_sequence(plan: Plan) -> tuple[tuple[str, str], ...]:
    """Secuencia de instalación para este plan: con Artwork/ solo si la tocó."""
    return _artwork_install_sequence(plan) + _BASE_INSTALL_SEQUENCE


class ApplyError(Exception):
    """Base de los errores durante apply."""


class StalePlanError(ApplyError):
    """El estado del iPod cambió desde que se construyó el plan; el plan está obsoleto."""


class PostCommitVerifyError(ApplyError):
    """La verificación post-commit falló tras instalar los archivos en el iPod."""


@dataclass(frozen=True)
class ApplyResult:
    success: bool
    backup_path: Optional[Path] = None
    restored_from_backup: bool = False
    first_write_committed: bool = False
    error: Optional[str] = None
    tracks_written: int = 0
    artwork_touched: bool = False
    artwork_tracks_count: int = 0
    artwork_skipped_count: int = 0


def default_commit_dir() -> Path:
    """``~/.cicada/ipod-commit`` (o $CICADA_HOME/ipod-commit)."""
    return cicada_home() / "ipod-commit"


def get_inflight_path(guid: str, *, commit_dir: Optional[Path | str] = None) -> Path:
    base = Path(commit_dir) if commit_dir is not None else default_commit_dir()
    return base / f"{_guid_hash(guid)}.json"


def set_inflight_marker(
    guid: str,
    backup_archive: Path,
    mount: Path,
    *,
    commit_dir: Optional[Path | str] = None,
    include_artwork: bool = False,
) -> Path:
    """Escribe atómicamente el marcador inflight en almacenamiento local.

    :param include_artwork: si el backup referenciado cubrió ``Artwork/`` —
        se persiste para que una recuperación cross-sesión
        (:func:`recover_inflight_commit`) pode esa raíz correctamente aunque
        no haya un ``Plan`` disponible en ese momento.
    """
    path = get_inflight_path(guid, commit_dir=commit_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "guid": guid,
        "backup_archive": str(backup_archive.resolve()),
        "mount": str(mount.resolve()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "include_artwork": include_artwork,
    }
    tmp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def clear_inflight_marker(guid: str, *, commit_dir: Optional[Path | str] = None) -> bool:
    """Elimina el marcador inflight tras completar con éxito el commit."""
    path = get_inflight_path(guid, commit_dir=commit_dir)
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_inflight_marker(guid: str, *, commit_dir: Optional[Path | str] = None) -> Optional[dict]:
    """Obtiene los datos del marcador inflight si existe, o None."""
    path = get_inflight_path(guid, commit_dir=commit_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Marcador inflight corrupto en %s: %s", path, exc)
        return None


def purge_staging_temps(mount: Path) -> None:
    """Elimina explícitamente cualquier archivo temporal `*.cicada-new` residual en el iPod."""
    itunes_dir = mount / "iPod_Control" / "iTunes"
    if not itunes_dir.is_dir():
        return
    for dirpath, _dirnames, filenames in os.walk(itunes_dir):
        for fn in filenames:
            if fn.endswith(".cicada-new"):
                p = Path(dirpath) / fn
                try:
                    assert_within_ipod_control(p, mount)
                    p.unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning("No se pudo purgar temporal %s: %s", p, exc)


def recover_inflight_commit(
    mount: Path | str,
    guid: str,
    *,
    commit_dir: Optional[Path | str] = None,
) -> bool:
    """Restaura el iPod desde el backup registrado si un commit previo fue interrumpido.

    Devuelve True si se ejecutó una recuperación con éxito, False si no había marcador.
    """
    marker = get_inflight_marker(guid, commit_dir=commit_dir)
    if not marker:
        return False

    archive_path = Path(marker["backup_archive"])
    resolved_mount = resolve_mount(expected_guid=guid, candidates=[mount])
    assert_writable(resolved_mount)

    logger.warning("Detectado commit incompleto para GUID %s. Ejecutando rollback desde %s...", guid, archive_path)
    if archive_path.is_file():
        restore_backup(archive_path, resolved_mount, include_artwork=marker.get("include_artwork", False))
    purge_staging_temps(resolved_mount)
    clear_inflight_marker(guid, commit_dir=commit_dir)
    return True


def apply(
    plan: Plan,
    *,
    mount: str | Path,
    device_info: DeviceInfo,
    consent_ack: bool = False,
    consent_dir: Optional[str | Path] = None,
    backups_dir: Optional[str | Path] = None,
    commit_dir: Optional[str | Path] = None,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> ApplyResult:
    """Ejecuta de forma atómica y verificada el plan sobre el iPod con rollback ante cualquier fallo."""

    def _progress(msg: str, frac: float) -> None:
        if on_progress is not None:
            try:
                on_progress(msg, frac)
            except Exception:
                pass

    _progress("Validando precondiciones", 0.0)

    resolved_mount = resolve_mount(expected_guid=plan.guid, candidates=[mount])
    assert_writable(resolved_mount)

    if not device_info.guid_is_write_safe:
        raise UnsafeDeviceError(
            f"Procedencia de GUID insegura para escribir: {device_info.guid_provenance!r}"
        )

    if plan.consent_needed:
        if not consent_ack:
            raise ConsentRequiredError(
                "La primera escritura en el iPod requiere consentimiento explícito para "
                "la advertencia de Music.app (consent_ack=True)."
            )
        record_music_app_consent(plan.guid, consent_dir=consent_dir)

    sequence = _install_sequence(plan)
    for stage_rel, target_rel in sequence:
        src = plan.staging_dir / stage_rel
        if not src.is_file():
            raise InconsistentArtifactsError(f"Falta el artefacto de staging requerido: {src}")
        if src.stat().st_size == 0 and not stage_rel.startswith("Artwork/"):
            raise InconsistentArtifactsError(f"El artefacto de staging está vacío: {src}")

    if not plan.pre_state.matches(resolved_mount):
        raise StalePlanError(
            "El estado de los archivos de base de datos en el iPod cambió después de generar el plan. "
            "Plan descartado para evitar sobrescribir mutaciones externas."
        )

    _progress("Creando backup de seguridad", 0.2)
    backup_path = create_backup(
        resolved_mount,
        mode=BackupMode.DB_ONLY,
        guid=plan.guid,
        backups_dir=backups_dir,
        include_artwork=plan.artwork_touched,
    )

    _progress("Transfiriendo archivos de base de datos", 0.4)
    staged_device_temps: list[Path] = []
    itunes_dir = resolved_mount / "iPod_Control" / "iTunes"
    itlp_dir = itunes_dir / "iTunes Library.itlp"
    itlp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for stage_rel, target_rel in sequence:
            src = plan.staging_dir / stage_rel
            dest = assert_within_ipod_control(resolved_mount / target_rel, resolved_mount)
            temp_on_device = dest.with_name(dest.name + ".cicada-new")
            dest.parent.mkdir(parents=True, exist_ok=True)

            with open(src, "rb") as sf, open(temp_on_device, "wb") as df:
                for chunk in iter(lambda: sf.read(1 << 16), b""):
                    df.write(chunk)
                flush_written_file(df)

            staged_device_temps.append(temp_on_device)
    except BaseException as exc:
        logger.exception("Fallo durante la copia a staging en device: %s", exc)
        for tmp in staged_device_temps:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _progress("Aplicando cambios de base de datos", 0.7)
    set_inflight_marker(
        plan.guid, backup_path, resolved_mount, commit_dir=commit_dir,
        include_artwork=plan.artwork_touched,
    )

    try:
        for stage_rel, target_rel in sequence:
            dest = assert_within_ipod_control(resolved_mount / target_rel, resolved_mount)
            temp_on_device = dest.with_name(dest.name + ".cicada-new")
            os.replace(temp_on_device, dest)

        for pdir in (itlp_dir, itunes_dir):
            try:
                dfd = os.open(str(pdir), os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except (OSError, PermissionError) as exc:
                logger.debug("fsync en directorio %s no soportado: %s", pdir, exc)

    except BaseException as exc:
        logger.exception("Error crítico durante Fase D (Commit). Disparando rollback inmediato: %s", exc)
        restore_backup(backup_path, resolved_mount, include_artwork=plan.artwork_touched)
        purge_staging_temps(resolved_mount)
        clear_inflight_marker(plan.guid, commit_dir=commit_dir)
        return ApplyResult(
            success=False,
            backup_path=backup_path,
            restored_from_backup=True,
            error=f"Fallo en commit (restaurado): {exc}",
        )

    _progress("Verificando consistencia post-escritura", 0.9)
    try:
        cdb_target = itunes_dir / "iTunesCDB"
        lib_data = load_ipod_library(str(cdb_target), mount=str(resolved_mount))
        if not lib_data or len(lib_data.get("mhlt", [])) != plan.tracks_count:
            raise PostCommitVerifyError(
                f"El número de pistas en iTunesCDB ({len(lib_data.get('mhlt', [])) if lib_data else -1}) "
                f"no coincide con el plan ({plan.tracks_count})."
            )

        if plan.checksum_type is ChecksumType.HASHAB:
            if not verify_hashab(cdb_target.read_bytes(), plan.firewire_id):
                raise PostCommitVerifyError("verify_hashab falló en el iTunesCDB recién commiteado.")

        for fn in ("Library.itdb", "Locations.itdb", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
            db_path = itlp_dir / fn
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            res = con.execute("PRAGMA integrity_check").fetchone()
            if not res or res[0] != "ok":
                con.close()
                raise PostCommitVerifyError(f"PRAGMA integrity_check falló en {fn}: {res}")
            con.close()

        if plan.artwork_touched:
            artworkdb_target = resolved_mount / "iPod_Control" / "Artwork" / "ArtworkDB"
            if not artworkdb_target.is_file():
                raise PostCommitVerifyError("ArtworkDB no está presente tras el commit.")
            parsed_entries = read_artworkdb(artworkdb_target.read_bytes())
            if len(parsed_entries) != plan.artwork_tracks_count:
                raise PostCommitVerifyError(
                    f"ArtworkDB instalado tiene {len(parsed_entries)} entradas, "
                    f"se esperaban {plan.artwork_tracks_count}."
                )
            parsed_img_ids = {e.img_id for e in parsed_entries}
            expected_img_ids = {t.mhii_link for t in plan.tracks if t.mhii_link}
            missing = expected_img_ids - parsed_img_ids
            if missing:
                raise PostCommitVerifyError(
                    f"Tracks referencian artwork_id_ref sin entrada en ArtworkDB: {sorted(missing)}"
                )

    except BaseException as exc:
        logger.exception("Verificación post-commit fallida. Disparando rollback inmediato: %s", exc)
        restore_backup(backup_path, resolved_mount, include_artwork=plan.artwork_touched)
        purge_staging_temps(resolved_mount)
        clear_inflight_marker(plan.guid, commit_dir=commit_dir)
        return ApplyResult(
            success=False,
            backup_path=backup_path,
            restored_from_backup=True,
            error=f"Verificación post-commit fallida (restaurado): {exc}",
        )

    _progress("Finalizado con éxito", 1.0)
    clear_inflight_marker(plan.guid, commit_dir=commit_dir)
    mark_first_write_committed(plan.guid, consent_dir=consent_dir)
    purge_staging_temps(resolved_mount)

    return ApplyResult(
        success=True,
        backup_path=backup_path,
        restored_from_backup=False,
        first_write_committed=plan.consent_needed,
        tracks_written=plan.tracks_count,
        artwork_touched=plan.artwork_touched,
        artwork_tracks_count=plan.artwork_tracks_count,
        artwork_skipped_count=plan.artwork_skipped_count,
    )
