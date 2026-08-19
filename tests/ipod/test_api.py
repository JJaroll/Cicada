"""Tests para los endpoints FastAPI del iPod (/api/ipod) — cicada/ipod/api.py."""
from __future__ import annotations

import plistlib
from pathlib import Path

import httpx
import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.core.main import app
from cicada.ipod.db.coordinator.consent import (
    default_consent_dir,
    record_music_app_consent,
    revoke_music_app_consent,
)
from cicada.ipod.db.coordinator.plan import create_plan
from cicada.ipod.db.models import PlaylistInfo
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"
ART_MP3 = Path(__file__).resolve().parents[1] / "fixtures" / "audio" / "with_art.mp3"


@pytest.fixture
def mock_ipod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mount = tmp_path / "ipod_mount"
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True, exist_ok=True)
    sie_data = plistlib.dumps({
        "FireWireGUID": GUID_STR,
        "FamilyID": 18,
        "SerialNumber": "C17X1234F19R",
        "ModelNumStr": "MD481",
    })
    (device_dir / "SysInfoExtended").write_bytes(sie_data)

    itunes_dir = mount / "iPod_Control" / "iTunes"
    itlp_dir = itunes_dir / "iTunes Library.itlp"
    itlp_dir.mkdir(parents=True, exist_ok=True)

    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(
        mount=mount,
        firewire_guid=GUID_STR,
        family="iPod Nano",
        generation="7th Gen",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance="disk",
        capabilities=caps,
    )

    init_tracks = [
        TrackInfo(
            title="Initial Track",
            artist="Initial Artist",
            album="Initial Album",
            location=":iPod_Control:Music:F00:INIT.mp3",
            db_track_id=100,
        )
    ]
    init_plan = create_plan(mount, init_tracks, device_info=dev)

    (itunes_dir / "iTunesCDB").write_bytes((init_plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((init_plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))

    return mount


#: dbid de 64 bits típico de random.getrandbits(64) — supera 2^53, el límite exacto
#: de un JS Number. Sirve para probar que el backend NO depende de que el dbid
#: llegue como int por JSON (el navegador lo redondearía); debe viajar como str.
BIG_DBID = 9223372036854774808


@pytest.fixture
def mock_ipod_with_playlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mount = tmp_path / "ipod_mount"
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True, exist_ok=True)
    (device_dir / "SysInfoExtended").write_bytes(plistlib.dumps({
        "FireWireGUID": GUID_STR, "FamilyID": 18,
        "SerialNumber": "C17X1234F19R", "ModelNumStr": "MD481",
    }))
    itunes_dir = mount / "iPod_Control" / "iTunes"
    itlp_dir = itunes_dir / "iTunes Library.itlp"
    itlp_dir.mkdir(parents=True, exist_ok=True)

    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(
        mount=mount, firewire_guid=GUID_STR, family="iPod Nano",
        generation="7th Gen", family_id=18, checksum=ChecksumType.HASHAB,
        guid_provenance="disk", capabilities=caps,
    )
    init_tracks = [
        TrackInfo(title="Existing Big", artist="A",
                 location=":iPod_Control:Music:F00:BIG.mp3", db_track_id=BIG_DBID),
    ]
    init_plan = create_plan(
        mount, init_tracks, device_info=dev,
        playlists=[PlaylistInfo(name="Mi Playlist", track_ids=[BIG_DBID], master=False)],
    )
    (itunes_dir / "iTunesCDB").write_bytes((init_plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((init_plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))
    return mount


@pytest.fixture
def async_client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_api_status_no_device(async_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [])
    resp = await async_client.get("/api/ipod/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "no_device"
    assert data["devices"] == []


@pytest.mark.asyncio
async def test_api_status_ready(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "ready"
    assert len(data["devices"]) == 1
    dev = data["devices"][0]
    assert dev["firewire_guid"] == GUID_STR
    assert dev["family"] == "iPod Nano"
    assert dev["guid_is_write_safe"] is True
    assert dev["music_app_consent_granted"] is False


@pytest.mark.asyncio
async def test_api_tracks_list(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/tracks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["guid"] == GUID_STR
    assert data["tracks_count"] == 1
    assert data["tracks"][0]["title"] == "Initial Track"


@pytest.mark.asyncio
async def test_api_plan_and_apply_flow(async_client: httpx.AsyncClient, mock_ipod: Path):
    new_tracks = [
        {
            "title": "New Song 1",
            "artist": "New Artist 1",
            "album": "New Album 1",
            "location": ":iPod_Control:Music:F00:N1.mp3",
            "db_track_id": 201,
        },
        {
            "title": "New Song 2",
            "artist": "New Artist 2",
            "album": "New Album 2",
            "location": ":iPod_Control:Music:F01:N2.mp3",
            "db_track_id": 202,
        },
    ]

    # 1. Generar plan dry-run
    resp_plan = await async_client.post("/api/ipod/plan", json={"tracks": new_tracks})
    assert resp_plan.status_code == 200
    plan_data = resp_plan.json()
    assert plan_data["guid"] == GUID_STR
    assert plan_data["tracks_count"] == 2
    assert plan_data["consent_needed"] is True
    plan_id = plan_data["plan_id"]

    # 2. Apply sin consent_ack falla con 403 Forbidden
    resp_apply_fail = await async_client.post("/api/ipod/apply", json={"plan_id": plan_id, "consent_ack": False})
    assert resp_apply_fail.status_code == 403
    assert resp_apply_fail.json()["detail"]["code"] == "CONSENT_REQUIRED"

    # 3. Apply con consent_ack tiene éxito
    resp_apply_ok = await async_client.post("/api/ipod/apply", json={"tracks": new_tracks, "consent_ack": True})
    assert resp_apply_ok.status_code == 200
    apply_data = resp_apply_ok.json()
    assert apply_data["success"] is True
    assert apply_data["tracks_written"] == 2
    assert apply_data["backup_path"] is not None

    # 4. Verificar que /tracks ahora refleja las 2 pistas
    resp_tracks = await async_client.get("/api/ipod/tracks")
    assert resp_tracks.status_code == 200
    assert resp_tracks.json()["tracks_count"] == 2


@pytest.mark.asyncio
async def test_api_plan_apply_preserva_playlists(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path
):
    # Regresión: el botón "Sincronizar" (plan/apply crudo, sin tocar audio) NO debe
    # borrar las playlists de usuario — antes create_plan() no recibía playlists=.
    resp_tracks = await async_client.get("/api/ipod/tracks")
    tracks = resp_tracks.json()["tracks"]
    assert tracks[0]["db_track_id"] == str(BIG_DBID)   # viaja como string, sin perder precisión

    resp_apply = await async_client.post("/api/ipod/apply", json={"tracks": tracks, "consent_ack": True})
    assert resp_apply.status_code == 200
    assert resp_apply.json()["success"] is True

    resp_pl = await async_client.get("/api/ipod/playlists")
    names = {p["title"] for p in resp_pl.json()["playlists"]}
    assert "Mi Playlist" in names
    pl = next(p for p in resp_pl.json()["playlists"] if p["title"] == "Mi Playlist")
    assert len(pl["tracks"]) == 1   # su pista sigue ahí (no quedó vacía)


@pytest.mark.asyncio
async def test_api_track_remove(async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path):
    resp_del = await async_client.post("/api/ipod/track/remove", json={
        "db_track_id": str(BIG_DBID), "consent_ack": True,
    })
    assert resp_del.status_code == 200
    assert resp_del.json()["success"] is True

    resp_tracks = await async_client.get("/api/ipod/tracks")
    assert resp_tracks.json()["tracks_count"] == 0

    resp_pl = await async_client.get("/api/ipod/playlists")
    pl = next(p for p in resp_pl.json()["playlists"] if p["title"] == "Mi Playlist")
    assert pl["tracks"] == []   # ya no referencia la pista borrada


@pytest.fixture
def mock_ipod_with_rating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mount = tmp_path / "ipod_mount"
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True, exist_ok=True)
    (device_dir / "SysInfoExtended").write_bytes(plistlib.dumps({
        "FireWireGUID": GUID_STR, "FamilyID": 18,
        "SerialNumber": "C17X1234F19R", "ModelNumStr": "MD481",
    }))
    itunes_dir = mount / "iPod_Control" / "iTunes"
    itlp_dir = itunes_dir / "iTunes Library.itlp"
    itlp_dir.mkdir(parents=True, exist_ok=True)

    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(
        mount=mount, firewire_guid=GUID_STR, family="iPod Nano",
        generation="7th Gen", family_id=18, checksum=ChecksumType.HASHAB,
        guid_provenance="disk", capabilities=caps,
    )
    init_tracks = [
        TrackInfo(title="Rated Track", location=":iPod_Control:Music:F00:R.mp3",
                 db_track_id=777, rating=80, play_count=5),
    ]
    init_plan = create_plan(mount, init_tracks, device_info=dev)
    (itunes_dir / "iTunesCDB").write_bytes((init_plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((init_plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))
    return mount


@pytest.mark.asyncio
async def test_api_sync_playback(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    resp = await async_client.post("/api/ipod/sync/playback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["guid"] == GUID_STR
    assert data["total_tracks_scanned"] == 1
    assert data["tracks_changed"] == 1
    assert data["ratings_updated_count"] == 1

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    state = db.get_playback_state(GUID_STR, 777)
    assert state is not None
    assert state.known_rating == 80

    # Segunda llamada: ya no hay cambios pendientes (línea base al día).
    resp2 = await async_client.post("/api/ipod/sync/playback")
    assert resp2.json()["tracks_changed"] == 0


@pytest.mark.asyncio
async def test_api_sync_playback_dry_run_no_persiste(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    resp = await async_client.post("/api/ipod/sync/playback", params={"dry_run": True})
    assert resp.status_code == 200
    assert resp.json()["ratings_updated_count"] == 1

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    assert db.get_playback_state(GUID_STR, 777) is None   # no persistió


@pytest.mark.asyncio
async def test_api_track_rate(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    resp = await async_client.post("/api/ipod/track/rate", json={"db_track_id": "777", "rating": 40})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    local = db.get_local_playback_state(GUID_STR, 777)
    assert local is not None
    assert local.local_rating == 40


@pytest.mark.asyncio
async def test_api_track_rate_fuera_de_rango(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    resp = await async_client.post("/api/ipod/track/rate", json={"db_track_id": "777", "rating": 150})
    assert resp.status_code == 400


async def _seed_conflict(async_client: httpx.AsyncClient, dbid: int, known: int, local: int):
    """Establece baseline=known y local_rating=local para dbid (el device
    ya tiene su rating real leído del Dynamic.itdb del fixture)."""
    from cicada.ipod.sync.state import (
        DeviceRecord,
        LocalPlaybackStateRecord,
        PlaybackStateRecord,
        SyncStateDB,
        default_sync_db_path,
    )
    db = SyncStateDB(default_sync_db_path())
    db.upsert_device(DeviceRecord(guid=GUID_STR))
    db.upsert_playback_state(PlaybackStateRecord(guid=GUID_STR, ipod_dbid=dbid, known_rating=known))
    db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID_STR, ipod_dbid=dbid, local_rating=local))


@pytest.mark.asyncio
async def test_api_conflicts_vacio_sin_local_playback_state(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    resp = await async_client.get("/api/ipod/conflicts")
    assert resp.status_code == 200
    assert resp.json() == {"conflicts": [], "count": 0}


@pytest.mark.asyncio
async def test_api_conflicts_lista_conflicto_real_con_titulo(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    # mock_ipod_with_rating: dbid=777, device rating=80 (real, leído del Dynamic.itdb).
    await _seed_conflict(async_client, 777, known=50, local=20)

    resp = await async_client.get("/api/ipod/conflicts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    c = data["conflicts"][0]
    assert c["ipod_dbid"] == "777"
    assert c["title"] == "Rated Track"
    assert c["known_rating"] == 50
    assert c["local_rating"] == 20
    assert c["device_rating"] == 80


@pytest.mark.asyncio
async def test_api_conflicts_resolve_local_gana(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    await _seed_conflict(async_client, 777, known=50, local=20)

    resp = await async_client.post("/api/ipod/conflicts/resolve", json={
        "ipod_dbid": "777", "resolution": "local", "consent_ack": True,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # El conflicto ya no aparece (baseline y local quedaron alineados).
    resp2 = await async_client.get("/api/ipod/conflicts")
    assert resp2.json()["count"] == 0

    resp_tracks = await async_client.get("/api/ipod/tracks")
    track = next(t for t in resp_tracks.json()["tracks"] if t["db_track_id"] == "777")
    assert track["rating"] == 20   # el iPod ahora tiene el valor LOCAL


@pytest.mark.asyncio
async def test_api_conflicts_resolve_device_gana_sin_consent(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    await _seed_conflict(async_client, 777, known=50, local=20)

    # resolution="device" no escribe en el iPod -> no debería requerir consent_ack.
    resp = await async_client.post("/api/ipod/conflicts/resolve", json={
        "ipod_dbid": "777", "resolution": "device", "consent_ack": False,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp_tracks = await async_client.get("/api/ipod/tracks")
    track = next(t for t in resp_tracks.json()["tracks"] if t["db_track_id"] == "777")
    assert track["rating"] == 80   # el iPod no cambió


@pytest.mark.asyncio
async def test_api_conflicts_resolve_sin_conflicto_404(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    resp = await async_client.post("/api/ipod/conflicts/resolve", json={
        "ipod_dbid": "777", "resolution": "local", "consent_ack": True,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_conflicts_resolve_resolution_invalida(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    resp = await async_client.post("/api/ipod/conflicts/resolve", json={
        "ipod_dbid": "777", "resolution": "coinflip", "consent_ack": True,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_conflicts_resolve_all_aplica_a_todos(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    await _seed_conflict(async_client, 777, known=50, local=20)

    resp = await async_client.post("/api/ipod/conflicts/resolve-all", json={
        "resolution": "local", "consent_ack": True,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp2 = await async_client.get("/api/ipod/conflicts")
    assert resp2.json()["count"] == 0


@pytest.mark.asyncio
async def test_api_conflicts_resolve_all_sin_conflictos_no_hace_nada(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    resp = await async_client.post("/api/ipod/conflicts/resolve-all", json={
        "resolution": "local", "consent_ack": True,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["tracks_written"] == 0


@pytest.mark.asyncio
async def test_api_apply_stale_plan_409(async_client: httpx.AsyncClient, mock_ipod: Path):
    tracks = [
        {
            "title": "Song",
            "location": ":iPod_Control:Music:F00:S.mp3",
        }
    ]
    resp_plan = await async_client.post("/api/ipod/plan", json={"tracks": tracks})
    assert resp_plan.status_code == 200
    plan_id = resp_plan.json()["plan_id"]

    # Mutar el disco para que el plan quede obsoleto
    (mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB").write_bytes(b"stale change")

    resp_apply = await async_client.post("/api/ipod/apply", json={"plan_id": plan_id, "consent_ack": True})
    assert resp_apply.status_code == 409
    assert resp_apply.json()["detail"]["code"] == "STALE_PLAN"


@pytest.mark.asyncio
async def test_api_playlists_returns_dbid_as_string(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path
):
    # GET /playlists debe exponer el dbid como string (no como Number: un dbid de
    # 64 bits pierde precisión al pasar por JSON->JS Number en el navegador real).
    resp = await async_client.get("/api/ipod/playlists")
    assert resp.status_code == 200
    pl = next(p for p in resp.json()["playlists"] if p["title"] == "Mi Playlist")
    assert pl["tracks"][0]["db_track_id"] == str(BIG_DBID)


@pytest.mark.asyncio
async def test_api_playlist_set_agrega_sin_perder_pistas_grandes(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path, tmp_path: Path
):
    # Regresión: al agregar una canción nueva a una playlist, la pista existente
    # (con dbid > 2^53, como los que genera random.getrandbits(64) en producción)
    # NO debe perderse. El dbid se envía como string, tal como lo hace ahora el
    # frontend, para no perder precisión.
    src = tmp_path / "nueva.mp3"
    src.write_bytes(b"AUDIO" * 40)

    resp = await async_client.post("/api/ipod/playlist/set", json={
        "playlist_name": "Mi Playlist",
        "items": [
            {"db_track_id": str(BIG_DBID)},
            {"source_path": str(src), "title": "Nueva", "filetype": "mp3"},
        ],
        "consent_ack": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    resp2 = await async_client.get("/api/ipod/playlists")
    pl = next(p for p in resp2.json()["playlists"] if p["title"] == "Mi Playlist")
    titles = {t["title"] for t in pl["tracks"]}
    assert titles == {"Existing Big", "Nueva"}   # la pista original NO se perdió


@pytest.mark.asyncio
async def test_api_consent_endpoints(async_client: httpx.AsyncClient, mock_ipod: Path):
    # GET inicial -> False
    resp = await async_client.get(f"/api/ipod/consent/{GUID_STR}")
    assert resp.status_code == 200
    assert resp.json()["has_consent"] is False

    # POST -> Otorgar
    resp_grant = await async_client.post(f"/api/ipod/consent/{GUID_STR}")
    assert resp_grant.status_code == 200
    assert resp_grant.json()["has_consent"] is True

    # GET -> True
    resp2 = await async_client.get(f"/api/ipod/consent/{GUID_STR}")
    assert resp2.status_code == 200
    assert resp2.json()["has_consent"] is True

    # DELETE -> Revocar
    resp_rev = await async_client.delete(f"/api/ipod/consent/{GUID_STR}")
    assert resp_rev.status_code == 200
    assert resp_rev.json()["has_consent"] is False


@pytest.mark.asyncio
async def test_api_backups_and_restore(async_client: httpx.AsyncClient, mock_ipod: Path):
    # Crear backup manual
    resp_bkp = await async_client.post("/api/ipod/backup", json={"full": False})
    assert resp_bkp.status_code == 200
    bkp_data = resp_bkp.json()
    assert bkp_data["guid"] == GUID_STR
    archive_path = bkp_data["path"]

    # Listar backups
    resp_list = await async_client.get("/api/ipod/backups")
    assert resp_list.status_code == 200
    assert len(resp_list.json()["backups"]) >= 1

    # Restaurar backup
    resp_rest = await async_client.post("/api/ipod/restore", json={"archive_path": archive_path})
    assert resp_rest.status_code == 200
    assert resp_rest.json()["success"] is True


# --------------------------------------------------------------------------- #
# Endpoints de soporte de la UI: imagen de modelo, storage, y stubs de media /
# playlists (deben ser HONESTOS: 501 para lo no implementado, no éxito falso).
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_api_status_incluye_imagen_y_storage(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/status")
    assert resp.status_code == 200
    dev = resp.json()["devices"][0]
    assert isinstance(dev["image_url"], str)
    assert dev["image_url"].startswith("/static/ipod_images/")
    st = dev["storage"]
    assert st is not None
    assert st["total_bytes"] >= st["used_bytes"] >= 0
    assert "formatted_total" in st


@pytest.mark.asyncio
async def test_api_scan_incluye_imagen_y_storage(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/scan")
    assert resp.status_code == 200
    ip = resp.json()["ipods"][0]
    assert ip["image_url"].startswith("/static/ipod_images/")
    assert ip["storage"] is not None


@pytest.mark.asyncio
async def test_api_storage_endpoint(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/storage")
    assert resp.status_code == 200
    st = resp.json()
    for k in ("total_bytes", "used_bytes", "free_bytes", "audio_bytes", "formatted_total"):
        assert k in st


@pytest.mark.asyncio
async def test_api_playlists_list(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get("/api/ipod/playlists")
    assert resp.status_code == 200
    data = resp.json()
    assert "playlists" in data and "count" in data


@pytest.mark.asyncio
@pytest.mark.parametrize("path,payload", [
    ("/api/ipod/playlists/create", {"name": "X"}),
    ("/api/ipod/playlists/import", {"source_name": "X", "tracks": []}),
])
async def test_api_playlist_writes_no_implementadas(async_client: httpx.AsyncClient, path, payload):
    resp = await async_client.post(path, json=payload)
    assert resp.status_code == 501
    assert resp.json()["detail"]["code"] == "NOT_IMPLEMENTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/ipod/photos/p1", "/api/ipod/videos/v1"])
async def test_api_delete_media_no_implementado(async_client: httpx.AsyncClient, path):
    resp = await async_client.delete(path)
    assert resp.status_code == 501
    assert resp.json()["detail"]["code"] == "NOT_IMPLEMENTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,key", [
    ("/api/ipod/photos", "photos"),
    ("/api/ipod/videos", "videos"),
    ("/api/ipod/podcasts", "podcasts"),
    ("/api/ipod/audiobooks", "audiobooks"),
])
async def test_api_media_placeholders_vacios(async_client: httpx.AsyncClient, path, key):
    resp = await async_client.get(path)
    assert resp.status_code == 200
    data = resp.json()
    assert data[key] == [] and data["count"] == 0


@pytest.mark.asyncio
async def test_api_media_sync_copia_y_escribe(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    src = tmp_path / "newlocal.mp3"
    src.write_bytes(b"AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Local New", "artist": "L",
                    "filetype": "mp3", "length_ms": 120000}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    # El audio se copió a Music/ y la base ahora incluye la pista nueva.
    assert list((mock_ipod / "iPod_Control" / "Music").rglob("*.mp3"))
    resp_tracks = await async_client.get("/api/ipod/tracks")
    titles = {t["title"] for t in resp_tracks.json()["tracks"]}
    assert "Local New" in titles


@pytest.mark.asyncio
async def test_api_media_sync_source_no_existe(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": "/no/existe/x.mp3", "title": "X"}],
        "consent_ack": True,
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "SOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_media_sync_consent_requerido(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    src = tmp_path / "s.mp3"
    src.write_bytes(b"A" * 20)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Y"}],
        "consent_ack": False,
    })
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "CONSENT_REQUIRED"


@pytest.mark.asyncio
async def test_api_media_sync_reports_artwork_counts(async_client: httpx.AsyncClient, mock_ipod: Path):
    """artwork_touched/tracks_count/skipped_count en la respuesta de
    /media/sync deben coincidir con el ArtworkDB REALMENTE instalado, no
    con un número fijo."""
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(ART_MP3), "title": "Con Arte", "artist": "A"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["artwork_touched"] is True
    assert data["artwork_tracks_count"] == 1
    assert data["artwork_skipped_count"] == 0

    from cicada.ipod.db.artwork.chunks import read_artworkdb
    artworkdb_bytes = (mock_ipod / "iPod_Control" / "Artwork" / "ArtworkDB").read_bytes()
    entries = read_artworkdb(artworkdb_bytes)
    assert len(entries) == data["artwork_tracks_count"]


@pytest.mark.asyncio
async def test_api_media_sync_without_artwork_reports_zero(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Un track sin carátula embebida (bytes crudos, sin tags) reporta 0/False."""
    src = tmp_path / "no_art.mp3"
    src.write_bytes(b"AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Sin Arte", "artist": "A"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["artwork_touched"] is False
    assert data["artwork_tracks_count"] == 0
    assert data["artwork_skipped_count"] == 0


@pytest.mark.asyncio
async def test_api_plan_apply_reports_artwork_counts_via_location(
    async_client: httpx.AsyncClient, mock_ipod: Path
):
    """/plan y /apply (el par TrackSchema, sin source_path) resuelven artwork
    vía `location` — el contrato real de round-trip, no de agregar audio
    nuevo. Los conteos reportados deben coincidir con el ArtworkDB instalado."""
    music_path = mock_ipod / "iPod_Control" / "Music" / "F02" / "ART.mp3"
    music_path.parent.mkdir(parents=True, exist_ok=True)
    music_path.write_bytes(ART_MP3.read_bytes())

    new_tracks = [{
        "title": "Con Arte", "artist": "A", "album": "Al",
        "location": ":iPod_Control:Music:F02:ART.mp3", "db_track_id": 501,
    }]

    resp_plan = await async_client.post("/api/ipod/plan", json={"tracks": new_tracks})
    assert resp_plan.status_code == 200
    plan_data = resp_plan.json()
    assert plan_data["artwork_touched"] is True
    assert plan_data["artwork_tracks_count"] == 1
    assert plan_data["artwork_skipped_count"] == 0

    resp_apply = await async_client.post(
        "/api/ipod/apply", json={"tracks": new_tracks, "consent_ack": True}
    )
    assert resp_apply.status_code == 200
    apply_data = resp_apply.json()
    assert apply_data["success"] is True
    assert apply_data["artwork_touched"] is True
    assert apply_data["artwork_tracks_count"] == 1
    assert apply_data["artwork_skipped_count"] == 0

    from cicada.ipod.db.artwork.chunks import read_artworkdb
    artworkdb_bytes = (mock_ipod / "iPod_Control" / "Artwork" / "ArtworkDB").read_bytes()
    entries = read_artworkdb(artworkdb_bytes)
    assert len(entries) == apply_data["artwork_tracks_count"]
