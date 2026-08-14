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
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"


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
