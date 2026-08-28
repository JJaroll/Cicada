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
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"
ART_MP3 = Path(__file__).resolve().parents[1] / "fixtures" / "audio" / "with_art.mp3"
ART_M4A = Path(__file__).resolve().parents[1] / "fixtures" / "audio" / "with_art.m4a"


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

    resp_plan = await async_client.post("/api/ipod/plan", json={"tracks": new_tracks})
    assert resp_plan.status_code == 200
    plan_data = resp_plan.json()
    assert plan_data["guid"] == GUID_STR
    assert plan_data["tracks_count"] == 2
    assert plan_data["consent_needed"] is True
    plan_id = plan_data["plan_id"]

    resp_apply_fail = await async_client.post("/api/ipod/apply", json={"plan_id": plan_id, "consent_ack": False})
    assert resp_apply_fail.status_code == 403
    assert resp_apply_fail.json()["detail"]["code"] == "CONSENT_REQUIRED"

    resp_apply_ok = await async_client.post("/api/ipod/apply", json={"tracks": new_tracks, "consent_ack": True})
    assert resp_apply_ok.status_code == 200
    apply_data = resp_apply_ok.json()
    assert apply_data["success"] is True
    assert apply_data["tracks_written"] == 2
    assert apply_data["backup_path"] is not None

    resp_tracks = await async_client.get("/api/ipod/tracks")
    assert resp_tracks.status_code == 200
    assert resp_tracks.json()["tracks_count"] == 2


@pytest.mark.asyncio
async def test_api_plan_apply_preserva_playlists(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path
):
    resp_tracks = await async_client.get("/api/ipod/tracks")
    tracks = resp_tracks.json()["tracks"]
    assert tracks[0]["db_track_id"] == str(BIG_DBID)

    resp_apply = await async_client.post("/api/ipod/apply", json={"tracks": tracks, "consent_ack": True})
    assert resp_apply.status_code == 200
    assert resp_apply.json()["success"] is True

    resp_pl = await async_client.get("/api/ipod/playlists")
    names = {p["title"] for p in resp_pl.json()["playlists"]}
    assert "Mi Playlist" in names
    pl = next(p for p in resp_pl.json()["playlists"] if p["title"] == "Mi Playlist")
    assert len(pl["tracks"]) == 1


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
    assert pl["tracks"] == []


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

    resp2 = await async_client.post("/api/ipod/sync/playback")
    assert resp2.json()["tracks_changed"] == 0


@pytest.mark.asyncio
async def test_api_sync_playback_dry_run_no_persiste(async_client: httpx.AsyncClient, mock_ipod_with_rating: Path):
    resp = await async_client.post("/api/ipod/sync/playback", params={"dry_run": True})
    assert resp.status_code == 200
    assert resp.json()["ratings_updated_count"] == 1

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    assert db.get_playback_state(GUID_STR, 777) is None


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

    resp2 = await async_client.get("/api/ipod/conflicts")
    assert resp2.json()["count"] == 0

    resp_tracks = await async_client.get("/api/ipod/tracks")
    track = next(t for t in resp_tracks.json()["tracks"] if t["db_track_id"] == "777")
    assert track["rating"] == 20


@pytest.mark.asyncio
async def test_api_conflicts_resolve_device_gana_sin_consent(
    async_client: httpx.AsyncClient, mock_ipod_with_rating: Path
):
    await _seed_conflict(async_client, 777, known=50, local=20)

    resp = await async_client.post("/api/ipod/conflicts/resolve", json={
        "ipod_dbid": "777", "resolution": "device", "consent_ack": False,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp_tracks = await async_client.get("/api/ipod/tracks")
    track = next(t for t in resp_tracks.json()["tracks"] if t["db_track_id"] == "777")
    assert track["rating"] == 80


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

    (mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB").write_bytes(b"stale change")

    resp_apply = await async_client.post("/api/ipod/apply", json={"plan_id": plan_id, "consent_ack": True})
    assert resp_apply.status_code == 409
    assert resp_apply.json()["detail"]["code"] == "STALE_PLAN"


@pytest.mark.asyncio
async def test_api_playlists_returns_dbid_as_string(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path
):
    resp = await async_client.get("/api/ipod/playlists")
    assert resp.status_code == 200
    pl = next(p for p in resp.json()["playlists"] if p["title"] == "Mi Playlist")
    assert pl["tracks"][0]["db_track_id"] == str(BIG_DBID)


@pytest.mark.asyncio
async def test_api_playlist_set_agrega_sin_perder_pistas_grandes(
    async_client: httpx.AsyncClient, mock_ipod_with_playlist: Path, tmp_path: Path
):
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
    assert titles == {"Existing Big", "Nueva"}


@pytest.mark.asyncio
async def test_api_consent_endpoints(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.get(f"/api/ipod/consent/{GUID_STR}")
    assert resp.status_code == 200
    assert resp.json()["has_consent"] is False

    resp_grant = await async_client.post(f"/api/ipod/consent/{GUID_STR}")
    assert resp_grant.status_code == 200
    assert resp_grant.json()["has_consent"] is True

    resp2 = await async_client.get(f"/api/ipod/consent/{GUID_STR}")
    assert resp2.status_code == 200
    assert resp2.json()["has_consent"] is True

    resp_rev = await async_client.delete(f"/api/ipod/consent/{GUID_STR}")
    assert resp_rev.status_code == 200
    assert resp_rev.json()["has_consent"] is False


@pytest.mark.asyncio
async def test_api_backups_and_restore(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp_bkp = await async_client.post("/api/ipod/backup", json={"full": False})
    assert resp_bkp.status_code == 200
    bkp_data = resp_bkp.json()
    assert bkp_data["guid"] == GUID_STR
    archive_path = bkp_data["path"]

    resp_list = await async_client.get("/api/ipod/backups")
    assert resp_list.status_code == 200
    assert len(resp_list.json()["backups"]) >= 1

    resp_rest = await async_client.post("/api/ipod/restore", json={"archive_path": archive_path})
    assert resp_rest.status_code == 200
    assert resp_rest.json()["success"] is True


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
@pytest.mark.parametrize("path", ["/api/ipod/podcasts", "/api/ipod/audiobooks", "/api/ipod/videos"])
async def test_api_podcasts_audiobooks_videos_sin_dispositivo_404(async_client: httpx.AsyncClient, monkeypatch, path):
    """Fase 5c/6c: a diferencia del placeholder anterior (siempre 200), ahora
    leen el dispositivo real — mismo comportamiento que /tracks si no hay
    ninguno montado."""
    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [])
    resp = await async_client.get(path)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MOUNT_NOT_FOUND"


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
@pytest.mark.parametrize("kind,expected_media_type", [
    ("podcast", 0x04),
    ("audiobook", 0x08),
])
async def test_api_media_sync_kind_escribe_media_type_y_flags_reales(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path, kind, expected_media_type,
):
    """Fase 5a: 'kind' debe llegar hasta el iTunesDB real, no solo a la
    respuesta HTTP. Round-trip byte a byte: se parsea el iTunesCDB
    escrito en disco (load_ipod_library), no se compara contra valores
    fijos ni contra la respuesta de otro endpoint de Cicada."""
    src = tmp_path / f"{kind}.mp3"
    src.write_bytes(b"AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{
            "source_path": str(src), "title": f"Un {kind}", "artist": "A",
            "kind": kind, "category": "Ficción",
        }],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == f"Un {kind}")
    assert track.get("media_type") == expected_media_type
    assert track.get("skip_when_shuffling") == 1
    assert track.get("remember_position") == 1
    assert track.get("Category") == "Ficción"
    if kind == "podcast":
        assert track.get("use_podcast_now_playing_flag") == 1
    else:
        assert track.get("use_podcast_now_playing_flag", 0) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected_media_type,expect_podcast_flags", [
    ("movie", 0x02, False),
    ("tv_show", 0x40, False),
    ("music_video", 0x20, False),
    ("video_podcast", 0x06, True),
])
async def test_api_media_sync_kind_video_escribe_media_type_y_flags_reales(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
    kind, expected_media_type, expect_podcast_flags,
):
    """Fase 6a: mismo rigor que 5a — round-trip real parseando el iTunesCDB
    escrito en disco, no la respuesta HTTP."""
    src = tmp_path / f"{kind}.m4v"
    src.write_bytes(b"VIDEO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": f"Un {kind}", "kind": kind}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == f"Un {kind}")
    assert track.get("media_type") == expected_media_type
    assert track.get("movie_flag") == 1
    if expect_podcast_flags:
        assert track.get("use_podcast_now_playing_flag") == 1
        assert track.get("skip_when_shuffling") == 1
        assert track.get("remember_position") == 1
    else:
        assert track.get("use_podcast_now_playing_flag", 0) == 0
        assert track.get("skip_when_shuffling", 0) == 0
        assert track.get("remember_position", 0) == 0


@pytest.mark.asyncio
async def test_api_media_sync_tv_show_escribe_season_episode_show_name(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
):
    src = tmp_path / "episodio.m4v"
    src.write_bytes(b"VIDEO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{
            "source_path": str(src), "title": "Piloto", "kind": "tv_show",
            "show_name": "Mi Serie", "season_number": 1, "episode_number": 3,
        }],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == "Piloto")
    assert track.get("media_type") == 0x40
    assert track.get("season_number") == 1
    assert track.get("episode_number") == 3
    assert track.get("Show") == "Mi Serie"


@pytest.mark.asyncio
async def test_api_media_sync_podcast_escribe_enclosure_y_rss_url(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
):
    """Investigado tras reportarse que un episodio de podcast sincronizado
    no aparecía en la app de Podcasts del dispositivo real, pese a estar
    correctamente presente en la biblioteca (playlist maestra, media_type,
    flags). iOpenPod (podcast_sync.py) puebla incondicionalmente
    podcast_enclosure_url/podcast_rss_url (MHOD 15/16) y artist/album con
    el nombre del programa — Cicada tenía el escritor vendorizado
    (write_mhod_podcast_url, Fase 5a) pero nunca lo conectaba desde
    sync_media(). Mismo rigor que toda la Fase 2: round-trip real
    parseando el iTunesCDB escrito en disco."""
    src = tmp_path / "episodio.mp3"
    src.write_bytes(b"PODCAST-AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{
            "source_path": str(src), "title": "Episodio con URLs", "kind": "podcast",
            "show_name": "Mi Programa",
            "podcast_enclosure_url": "https://example.com/feed/episodio.mp3",
            "podcast_rss_url": "https://example.com/feed.xml",
        }],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == "Episodio con URLs")
    assert track.get("Podcast Enclosure URL") == "https://example.com/feed/episodio.mp3"
    assert track.get("Podcast RSS URL") == "https://example.com/feed.xml"
    # Fallback tipo iOpenPod: sin artist/album explícitos, se usa el
    # nombre del programa — no debe quedar vacío para un episodio.
    assert track.get("Artist") == "Mi Programa"
    assert track.get("Album") == "Mi Programa"


@pytest.mark.asyncio
async def test_api_media_sync_podcast_respeta_artist_album_explicitos(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
):
    """El fallback a show_name no debe pisar un artist/album que el
    caller sí haya mandado explícitamente."""
    src = tmp_path / "episodio2.mp3"
    src.write_bytes(b"PODCAST-AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{
            "source_path": str(src), "title": "Episodio con Artist Propio", "kind": "podcast",
            "show_name": "Mi Programa", "artist": "Conductor Real", "album": "Temporada 2",
        }],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == "Episodio con Artist Propio")
    assert track.get("Artist") == "Conductor Real"
    assert track.get("Album") == "Temporada 2"


@pytest.mark.asyncio
async def test_api_media_sync_video_reusa_pipeline_de_artwork_existente(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
):
    """Fase 6b: verificar (no construir) que un video con carátula embebida
    (covr atom, mismo contenedor MP4 que .m4a) reutiliza el pipeline de
    artwork de Fase 4a-4d sin ningún cambio de código — create_plan() no
    filtra por media_type al resolver fuentes de arte."""
    import shutil
    src = tmp_path / "pelicula.m4v"
    shutil.copyfile(ART_M4A, src)

    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Con Arte De Video", "kind": "movie"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["artwork_touched"] is True
    assert data["artwork_tracks_count"] == 1

    from cicada.ipod.db.artwork.chunks import read_artworkdb
    artworkdb_bytes = (mock_ipod / "iPod_Control" / "Artwork" / "ArtworkDB").read_bytes()
    entries = read_artworkdb(artworkdb_bytes)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_api_videos_lista_plana_con_metadata_de_serie(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Fase 6c: /videos debe reflejar una biblioteca REAL escrita por
    apply() (no un fixture a mano) — película + episodio de serie, en
    lista plana (sin agrupar, así lo consume el frontend)."""
    movie = tmp_path / "pelicula.m4v"
    movie.write_bytes(b"VIDEO" * 40)
    episode = tmp_path / "episodio.m4v"
    episode.write_bytes(b"VIDEO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [
            {"source_path": str(movie), "title": "Una Pelicula", "kind": "movie", "length_ms": 5400000},
            {"source_path": str(episode), "title": "Piloto", "kind": "tv_show",
             "show_name": "Mi Serie", "season_number": 1, "episode_number": 1, "length_ms": 1500000},
        ],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/videos")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    by_title = {v["title"]: v for v in data["videos"]}
    assert by_title["Una Pelicula"]["kind"] == "movie"
    assert by_title["Una Pelicula"]["duration_ms"] == 5400000
    assert by_title["Piloto"]["kind"] == "tv_show"
    assert by_title["Piloto"]["show_name"] == "Mi Serie"
    assert by_title["Piloto"]["season_number"] == 1
    assert by_title["Piloto"]["episode_number"] == 1


@pytest.mark.asyncio
async def test_api_videos_no_incluye_video_podcast(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """video_podcast pertenece a /podcasts, no a /videos — evita que la
    misma pista aparezca duplicada en dos categorías del frontend."""
    src = tmp_path / "episodio_video.m4v"
    src.write_bytes(b"VIDEO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Episodio En Video",
                    "album": "Mi Video Podcast", "kind": "video_podcast"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/videos")
    assert resp.json() == {"videos": [], "count": 0}

    resp = await async_client.get("/api/ipod/podcasts")
    data = resp.json()
    assert data["count"] == 1
    assert data["podcasts"][0]["name"] == "Mi Video Podcast"
    assert data["podcasts"][0]["episodes"][0]["title"] == "Episodio En Video"


@pytest.mark.asyncio
async def test_api_video_delete_real_borra_pista_y_audio(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Fase 6c: DELETE /videos/{id} debe borrar de verdad (base + audio),
    no un mock local — mismo mecanismo genérico que POST /track/remove
    (Fase 3), aquí solo se traduce el id de la URL."""
    src = tmp_path / "para_borrar.m4v"
    src.write_bytes(b"VIDEO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Para Borrar", "kind": "movie"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/videos")
    video_id = resp.json()["videos"][0]["id"]

    resp = await async_client.delete(f"/api/ipod/videos/{video_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    assert "Para Borrar" not in {t.get("Title") for t in lib["mhlt"]}
    assert not list((mock_ipod / "iPod_Control" / "Music").rglob("*.m4v"))


@pytest.mark.asyncio
async def test_api_video_delete_inexistente_404(async_client: httpx.AsyncClient, mock_ipod: Path):
    resp = await async_client.delete("/api/ipod/videos/999999999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "TRACK_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_media_sync_kind_music_no_cambia_comportamiento_previo(
    async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path,
):
    """'kind' omitido (o 'music' explícito) debe seguir dando el mismo
    resultado que antes de Fase 5a: sin regresión para el camino existente."""
    src = tmp_path / "music.mp3"
    src.write_bytes(b"AUDIO-BYTES" * 50)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Cancion Normal", "artist": "A"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    from cicada.ipod.db.shared.constants import MEDIA_TYPE_AUDIO
    lib = load_ipod_library(
        str(mock_ipod / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mock_ipod),
    )
    track = next(t for t in lib["mhlt"] if t.get("Title") == "Cancion Normal")
    assert track.get("media_type") == MEDIA_TYPE_AUDIO
    assert track.get("skip_when_shuffling", 0) == 0
    assert track.get("remember_position", 0) == 0
    assert track.get("use_podcast_now_playing_flag", 0) == 0


def _build_nero_chpl_m4b(path: Path, chapters: list[tuple[int, str]]) -> None:
    import struct
    body = bytes([0]) + bytes(4) + bytes([len(chapters)])
    for start_ms, title in chapters:
        title_bytes = title.encode("utf-8")
        body += struct.pack(">Q", start_ms * 10_000) + bytes([len(title_bytes)]) + title_bytes
    def atom(fourcc: bytes, b: bytes) -> bytes:
        return struct.pack(">I", 8 + len(b)) + fourcc + b
    path.write_bytes(atom(b"moov", atom(b"udta", atom(b"chpl", body))))


@pytest.mark.asyncio
async def test_api_podcasts_agrupa_episodios_por_programa(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Fase 5c: /podcasts debe reflejar una biblioteca REAL escrita por
    apply() a través del pipeline completo (/media/sync), no un fixture
    armado a mano — dos episodios del mismo programa (mismo Album) deben
    agruparse juntos."""
    ep1 = tmp_path / "ep1.mp3"
    ep1.write_bytes(b"AUDIO" * 40)
    ep2 = tmp_path / "ep2.mp3"
    ep2.write_bytes(b"AUDIO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [
            {"source_path": str(ep1), "title": "Episodio 1", "album": "Radio Ambulante", "kind": "podcast"},
            {"source_path": str(ep2), "title": "Episodio 2", "album": "Radio Ambulante", "kind": "podcast"},
        ],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/podcasts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    pod = data["podcasts"][0]
    assert pod["name"] == "Radio Ambulante"
    assert {ep["title"] for ep in pod["episodes"]} == {"Episodio 1", "Episodio 2"}


@pytest.mark.asyncio
async def test_api_podcasts_no_incluye_musica_normal(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    src = tmp_path / "cancion.mp3"
    src.write_bytes(b"AUDIO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{"source_path": str(src), "title": "Una Cancion"}],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    resp = await async_client.get("/api/ipod/podcasts")
    assert resp.json() == {"podcasts": [], "count": 0}


@pytest.mark.asyncio
async def test_api_audiobooks_expande_capitulos_embebidos_de_una_pista(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Audiolibro de un solo archivo (.m4b) con capítulos Nero embebidos:
    /audiobooks debe expandir chapter_data, calculando la duración de cada
    capítulo a partir de los startpos consecutivos (chapter_data no trae
    duración explícita)."""
    src = tmp_path / "libro.m4b"
    _build_nero_chpl_m4b(src, [(0, "Capitulo 1"), (60000, "Capitulo 2"), (100000, "Capitulo 3")])
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [{
            "source_path": str(src), "title": "Un Libro", "artist": "Un Autor",
            "album": "Un Libro", "kind": "audiobook", "length_ms": 150000,
        }],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/audiobooks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    ab = data["audiobooks"][0]
    assert ab["title"] == "Un Libro"
    assert ab["author"] == "Un Autor"
    assert [(c["title"], c["duration_ms"]) for c in ab["chapters"]] == [
        ("Capitulo 1", 60000), ("Capitulo 2", 40000), ("Capitulo 3", 50000),
    ]


@pytest.mark.asyncio
async def test_api_audiobooks_multi_pista_usa_cada_pista_como_capitulo(async_client: httpx.AsyncClient, mock_ipod: Path, tmp_path: Path):
    """Formato alterno real (iTunes/iOpenPod): un audiolibro partido en
    varias pistas del mismo Album, sin chapter_data embebido — cada pista
    ES un capítulo, ordenadas por track_number."""
    part2 = tmp_path / "parte2.mp3"
    part2.write_bytes(b"AUDIO" * 40)
    part1 = tmp_path / "parte1.mp3"
    part1.write_bytes(b"AUDIO" * 40)
    resp = await async_client.post("/api/ipod/media/sync", json={
        "tracks": [
            {"source_path": str(part2), "title": "Parte 2", "album": "Multi Libro",
             "artist": "Autor", "kind": "audiobook", "track_number": 2, "length_ms": 30000},
            {"source_path": str(part1), "title": "Parte 1", "album": "Multi Libro",
             "artist": "Autor", "kind": "audiobook", "track_number": 1, "length_ms": 20000},
        ],
        "consent_ack": True,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    resp = await async_client.get("/api/ipod/audiobooks")
    data = resp.json()
    ab = next(a for a in data["audiobooks"] if a["title"] == "Multi Libro")
    assert [(c["title"], c["duration_ms"]) for c in ab["chapters"]] == [
        ("Parte 1", 20000), ("Parte 2", 30000),
    ]


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
