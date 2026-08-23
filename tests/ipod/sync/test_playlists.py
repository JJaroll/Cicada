"""Tests para cicada/ipod/sync/playlists.py — Sincronización y preservación de playlists."""
from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.coordinator.apply import apply
from cicada.ipod.db.coordinator.plan import create_plan
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.mhod_spl_writer import SmartPlaylistPrefs, SmartPlaylistRules
from cicada.ipod.db.writer.mhyp_writer import PlaylistInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo
from cicada.ipod.sync.playlists import (
    LocalPlaylist,
    PreparedPlaylists,
    extract_smart_playlists_for_preservation,
    prepare_all_playlists,
    prepare_standard_playlists,
    record_playlists_in_db,
)
from cicada.ipod.sync.state import (
    DeviceRecord,
    PlaylistMapRecord,
    SyncStateDB,
    TrackMapRecord,
)

GUID = "000A27002484DDFB"


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncStateDB:
    db = SyncStateDB(tmp_path / "ipod.db")
    db.upsert_device(DeviceRecord(guid=GUID))
    db.upsert_track_maps(
        [
            TrackMapRecord(guid=GUID, ipod_dbid=201, local_path="/music/song1.mp3"),
            TrackMapRecord(guid=GUID, ipod_dbid=202, local_path="/music/song2.mp3"),
            TrackMapRecord(guid=GUID, ipod_dbid=203, local_path="/music/song3.mp3"),
        ]
    )
    return db


@pytest.fixture
def mock_ipod_with_smart_playlist(tmp_path: Path) -> Path:
    mount = tmp_path / "ipod_mount"
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True, exist_ok=True)
    sie_data = plistlib.dumps({
        "FireWireGUID": GUID,
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
        firewire_guid=GUID,
        family="iPod Nano",
        generation="7th Gen",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance="disk",
        capabilities=caps,
    )

    init_tracks = [
        TrackInfo(
            title="Track One",
            artist="Artist One",
            album="Album One",
            location=":iPod_Control:Music:F00:T1.mp3",
            db_track_id=201,
        ),
        TrackInfo(
            title="Track Two",
            artist="Artist Two",
            album="Album Two",
            location=":iPod_Control:Music:F01:T2.mp3",
            db_track_id=202,
        ),
    ]

    smart_prefs = SmartPlaylistPrefs(live_update=True, check_rules=True, check_limits=False)
    smart_rules = SmartPlaylistRules(conjunction="AND", rules=[])
    smart_pl = PlaylistInfo(
        name="Top 25 Most Played",
        track_ids=[201, 202],
        playlist_id=999001,
        smart_prefs=smart_prefs,
        smart_rules=smart_rules,
        raw_mhod55=b"test_plist_blob",
    )

    plan = create_plan(mount, init_tracks, device_info=dev, smart_playlists=[smart_pl])

    (itunes_dir / "iTunesCDB").write_bytes((plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    return mount


def test_prepare_standard_playlists_with_sync_db(sync_db: SyncStateDB):
    local_pls = [
        LocalPlaylist(name="Rock Hits", track_paths=["/music/song1.mp3", "/music/song3.mp3"]),
        LocalPlaylist(name="Chill", track_paths=["/music/song2.mp3"], playlist_id=777888),
    ]

    pls, unresolved = prepare_standard_playlists(local_pls, GUID, sync_db=sync_db)
    assert unresolved == 0
    assert len(pls) == 2

    assert pls[0].name == "Rock Hits"
    assert pls[0].track_ids == [201, 203]
    assert pls[0].playlist_id is not None
    assert pls[0].playlist_id > 0

    assert pls[1].name == "Chill"
    assert pls[1].track_ids == [202]
    assert pls[1].playlist_id == 777888


def test_prepare_standard_playlists_unresolved_tracks(sync_db: SyncStateDB):
    local_pls = [
        LocalPlaylist(
            name="Mix",
            track_paths=["/music/song1.mp3", "/music/non_existent.mp3"],
        )
    ]

    pls, unresolved = prepare_standard_playlists(local_pls, GUID, sync_db=sync_db)
    assert unresolved == 1
    assert len(pls) == 1
    assert pls[0].track_ids == [201]


def test_extract_smart_playlists_preservation(mock_ipod_with_smart_playlist: Path):
    smart_pls = extract_smart_playlists_for_preservation(mock_ipod_with_smart_playlist)
    assert len(smart_pls) >= 1

    top25 = next(p for p in smart_pls if p.name == "Top 25 Most Played")
    assert top25.is_smart is True
    assert top25.smart_prefs is not None
    assert top25.smart_rules is not None
    assert top25.playlist_id is not None
    assert len(top25.track_ids) == 2


def test_prepare_all_playlists_unified(mock_ipod_with_smart_playlist: Path, sync_db: SyncStateDB):
    local_pls = [
        LocalPlaylist(name="Favorites", track_paths=["/music/song1.mp3", "/music/song2.mp3"]),
    ]

    prep = prepare_all_playlists(
        mount=mock_ipod_with_smart_playlist,
        guid=GUID,
        local_playlists=local_pls,
        sync_db=sync_db,
        preserve_smart_playlists=True,
    )

    assert len(prep.standard_playlists) == 1
    assert prep.standard_playlists[0].name == "Favorites"
    assert len(prep.smart_playlists) >= 1
    assert any(p.name == "Top 25 Most Played" for p in prep.smart_playlists)
    assert len(prep.all_playlists) == len(prep.standard_playlists) + len(prep.smart_playlists)


def test_record_playlists_in_db(sync_db: SyncStateDB):
    pls = [
        PlaylistInfo(name="Workout", track_ids=[201, 202], playlist_id=10101),
        PlaylistInfo(
            name="Top 25",
            track_ids=[201],
            playlist_id=20202,
            smart_prefs=SmartPlaylistPrefs(),
            smart_rules=SmartPlaylistRules(),
        ),
    ]

    record_playlists_in_db(GUID, pls, sync_db)

    stored = sync_db.list_playlists_map(GUID)
    assert len(stored) == 2
    workout = next(p for p in stored if p.name == "Workout")
    assert workout.playlist_id == 10101
    assert workout.is_smart is False
    assert workout.track_count == 2

    top25 = next(p for p in stored if p.name == "Top 25")
    assert top25.playlist_id == 20202
    assert top25.is_smart is True


def test_playlists_integration_with_plan_and_apply(
    mock_ipod_with_smart_playlist: Path,
    sync_db: SyncStateDB,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    mount = mock_ipod_with_smart_playlist
    dev = DeviceInfo(
        mount=mount,
        firewire_guid=GUID,
        family="iPod Nano",
        generation="7th Gen",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance="disk",
        capabilities=capabilities_for_family_gen("iPod Nano", "7th Gen"),
    )

    local_pls = [
        LocalPlaylist(name="My Roadtrip Mix", track_paths=["/music/song1.mp3", "/music/song2.mp3"]),
    ]

    prep = prepare_all_playlists(
        mount=mount,
        guid=GUID,
        local_playlists=local_pls,
        sync_db=sync_db,
        preserve_smart_playlists=True,
    )

    tracks = [
        TrackInfo(
            title="Track One",
            artist="Artist One",
            album="Album One",
            location=":iPod_Control:Music:F00:T1.mp3",
            db_track_id=201,
        ),
        TrackInfo(
            title="Track Two",
            artist="Artist Two",
            album="Album Two",
            location=":iPod_Control:Music:F01:T2.mp3",
            db_track_id=202,
        ),
    ]

    consent_dir = tmp_path / "consent"
    backups_dir = tmp_path / "backups"
    commit_dir = tmp_path / "commit"

    plan = create_plan(
        mount,
        tracks,
        device_info=dev,
        playlists=prep.standard_playlists,
        smart_playlists=prep.smart_playlists,
        consent_dir=consent_dir,
    )

    res = apply(
        plan,
        mount=mount,
        device_info=dev,
        consent_ack=True,
        consent_dir=consent_dir,
        backups_dir=backups_dir,
        commit_dir=commit_dir,
    )

    assert res.success is True
    assert res.tracks_written == 2

    record_playlists_in_db(GUID, prep.all_playlists, sync_db)
    assert len(sync_db.list_playlists_map(GUID)) >= 2

    cdb_path = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    lib = load_ipod_library(str(cdb_path), mount=str(mount))
    all_pls = lib.get("mhlp", []) + lib.get("mhlp_smart", [])
    mhyp_names = [p.get("name") or p.get("Title") for p in all_pls]
    assert "My Roadtrip Mix" in mhyp_names
    assert "Top 25 Most Played" in mhyp_names
