"""Test de la orquestación sync_media_to_ipod: copia audio + reescribe la base.

Requiere wasmtime (la base se firma con HASHAB). Monta un iPod falso con una base
inicial de 1 pista y añade una pista nueva (con audio local), verificando que el
MP3 se copió a Music/ y que la base reescrita contiene ambas.
"""
import plistlib
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.coordinator.media import sync_media_to_ipod
from cicada.ipod.db.coordinator.plan import create_plan
from cicada.ipod.db.models import PlaylistInfo, TrackInfo
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"


def _build_ipod(tmp_path, monkeypatch, tracks, playlists):
    mount = tmp_path / "ipod_mount"
    (mount / "iPod_Control" / "Device").mkdir(parents=True)
    (mount / "iPod_Control" / "Music").mkdir(parents=True)
    (mount / "iPod_Control" / "Device" / "SysInfoExtended").write_bytes(
        plistlib.dumps({"FireWireGUID": GUID_STR, "FamilyID": 18,
                        "SerialNumber": "C17X1234F19R", "ModelNumStr": "MD481"})
    )
    itunes = mount / "iPod_Control" / "iTunes"
    itlp = itunes / "iTunes Library.itlp"
    itlp.mkdir(parents=True)
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(mount=mount, firewire_guid=GUID_STR, family="iPod Nano",
                     generation="7th Gen", family_id=18, checksum=ChecksumType.HASHAB,
                     guid_provenance="disk", capabilities=caps)
    init = create_plan(mount, tracks, device_info=dev, playlists=playlists)
    (itunes / "iTunesCDB").write_bytes((init.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk",
               "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp / fn).write_bytes((init.staging_dir / "iTunes Library.itlp" / fn).read_bytes())
    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "home"))
    return mount, dev


@pytest.fixture
def ipod_with_db(tmp_path, monkeypatch):
    return _build_ipod(
        tmp_path, monkeypatch,
        [TrackInfo(title="Existing", artist="A",
                   location=":iPod_Control:Music:F00:INIT.mp3", db_track_id=100)],
        [PlaylistInfo(name="Mi Playlist", track_ids=[100], master=False)],
    )


def test_update_ipod_playlist_reordena(tmp_path, monkeypatch):
    from cicada.ipod.db.coordinator.media import update_ipod_playlist
    mount, dev = _build_ipod(
        tmp_path, monkeypatch,
        [TrackInfo(title="A", location=":iPod_Control:Music:F00:A.mp3", db_track_id=100),
         TrackInfo(title="B", location=":iPod_Control:Music:F00:B.mp3", db_track_id=200)],
        [PlaylistInfo(name="PL", track_ids=[100, 200], master=False)],
    )
    res = update_ipod_playlist(mount, "PL", [200, 100], device_info=dev, consent_ack=True)
    assert res.success is True
    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    pl = next(p for p in lib["mhlp"] if p.get("Title") == "PL")
    tid2db = {t.get("track_id"): t.get("db_track_id") for t in lib["mhlt"]}
    order = [tid2db.get(it.get("track_id")) for it in pl.get("items", [])]
    assert order == [200, 100]   # nuevo orden persistido
    # las 2 pistas siguen existiendo
    assert {t.get("Title") for t in lib["mhlt"]} == {"A", "B"}


def test_set_ipod_playlist_agrega_y_reordena(tmp_path, monkeypatch):
    from cicada.ipod.db.coordinator.media import set_ipod_playlist
    mount, dev = _build_ipod(
        tmp_path, monkeypatch,
        [TrackInfo(title="A", location=":iPod_Control:Music:F00:A.mp3", db_track_id=100),
         TrackInfo(title="B", location=":iPod_Control:Music:F00:B.mp3", db_track_id=200)],
        [PlaylistInfo(name="PL", track_ids=[100, 200], master=False)],
    )
    src = mount.parent / "added.mp3"
    src.write_bytes(b"AUDIO-NEW" * 20)

    items = [
        {"db_track_id": 200},
        {"source_path": str(src), "title": "Added", "artist": "C", "filetype": "mp3"},
        {"db_track_id": 100},
    ]
    res = set_ipod_playlist(mount, "PL", items, device_info=dev, consent_ack=True)
    assert res.success is True

    # El audio nuevo se copió.
    assert any(p.read_bytes() == src.read_bytes()
               for p in (mount / "iPod_Control" / "Music").rglob("*.mp3"))

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    pl = next(p for p in lib["mhlp"] if p.get("Title") == "PL")
    tid2db = {t.get("track_id"): t.get("db_track_id") for t in lib["mhlt"]}
    order = [tid2db.get(it.get("track_id")) for it in pl.get("items", [])]
    title_by_db = {t.get("db_track_id"): t.get("Title") for t in lib["mhlt"]}
    ordered_titles = [title_by_db.get(db) for db in order]
    assert ordered_titles == ["B", "Added", "A"]   # orden y pista nueva persistidos


def test_push_ratings_to_ipod_actualiza_una_pista(ipod_with_db):
    from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
    mount, dev = ipod_with_db

    res = push_ratings_to_ipod(mount, {100: 60}, device_info=dev, consent_ack=True)
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    track = next(t for t in lib["mhlt"] if t.get("db_track_id") == 100)
    assert track.get("rating") == 60
    # La playlist existente se preservó (no es lo que estamos tocando aquí).
    assert any(p.get("Title") == "Mi Playlist" for p in lib["mhlp"])


def test_push_ratings_to_ipod_batch_multiples_pistas(tmp_path, monkeypatch):
    from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
    mount, dev = _build_ipod(
        tmp_path, monkeypatch,
        [TrackInfo(title="A", location=":iPod_Control:Music:F00:A.mp3", db_track_id=100, rating=20),
         TrackInfo(title="B", location=":iPod_Control:Music:F00:B.mp3", db_track_id=200, rating=40)],
        [],
    )
    res = push_ratings_to_ipod(mount, {100: 80, 200: 100}, device_info=dev, consent_ack=True)
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    ratings = {t.get("db_track_id"): t.get("rating") for t in lib["mhlt"]}
    assert ratings[100] == 80
    assert ratings[200] == 100


def test_push_ratings_to_ipod_dbid_inexistente_falla(ipod_with_db):
    from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
    mount, dev = ipod_with_db
    with pytest.raises(ValueError):
        push_ratings_to_ipod(mount, {999999: 80}, device_info=dev, consent_ack=True)


def test_push_ratings_to_ipod_ignora_dbid_ausente_si_hay_otro_valido(ipod_with_db):
    from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
    mount, dev = ipod_with_db
    # 100 existe, 999999 no -> no debe fallar, solo aplica lo que existe.
    res = push_ratings_to_ipod(mount, {100: 60, 999999: 80}, device_info=dev, consent_ack=True)
    assert res.success is True
    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    track = next(t for t in lib["mhlt"] if t.get("db_track_id") == 100)
    assert track.get("rating") == 60


def test_push_ratings_to_ipod_consent_requerido(ipod_with_db):
    from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    mount, dev = ipod_with_db
    with pytest.raises(ConsentRequiredError):
        push_ratings_to_ipod(mount, {100: 60}, device_info=dev, consent_ack=False)


def test_remove_track_from_ipod_borra_pista_audio_y_referencias(tmp_path, monkeypatch):
    from cicada.ipod.db.coordinator.media import remove_track_from_ipod
    mount, dev = _build_ipod(
        tmp_path, monkeypatch,
        [TrackInfo(title="A", location=":iPod_Control:Music:F00:A.mp3", db_track_id=100),
         TrackInfo(title="B", location=":iPod_Control:Music:F00:B.mp3", db_track_id=200)],
        [PlaylistInfo(name="PL", track_ids=[100, 200], master=False)],
    )
    music_dir = mount / "iPod_Control" / "Music" / "F00"
    music_dir.mkdir(parents=True, exist_ok=True)
    (music_dir / "A.mp3").write_bytes(b"AUDIO-A")
    (music_dir / "B.mp3").write_bytes(b"AUDIO-B")

    res = remove_track_from_ipod(mount, 100, device_info=dev, consent_ack=True)
    assert res.success is True

    # El audio de la pista borrada ya no está; el de la otra sigue.
    assert not (music_dir / "A.mp3").exists()
    assert (music_dir / "B.mp3").exists()

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    assert {t.get("Title") for t in lib["mhlt"]} == {"B"}   # A ya no está en la base

    pl = next(p for p in lib["mhlp"] if p.get("Title") == "PL")
    tid2db = {t.get("track_id"): t.get("db_track_id") for t in lib["mhlt"]}
    remaining = [tid2db.get(it.get("track_id")) for it in pl.get("items", [])]
    assert remaining == [200]   # la playlist ya no referencia la pista borrada


def test_remove_track_from_ipod_inexistente_falla(ipod_with_db):
    from cicada.ipod.db.coordinator.media import remove_track_from_ipod
    mount, dev = ipod_with_db
    with pytest.raises(ValueError):
        remove_track_from_ipod(mount, 999999, device_info=dev, consent_ack=True)


def test_plan_sin_playlists_param_preserva_via_preserve_existing_playlists(ipod_with_db):
    # Regresión: /plan y /apply (usados por el botón "Sincronizar" crudo) escribían
    # la base sin pasar playlists a create_plan, borrando todas las de usuario.
    from cicada.ipod.db.coordinator.media import preserve_existing_playlists
    mount, dev = ipod_with_db
    regular, smart = preserve_existing_playlists(mount)
    assert any(p.name == "Mi Playlist" and p.track_ids == [100] for p in regular)


def test_sync_media_copia_audio_y_escribe_db(ipod_with_db):
    mount, dev = ipod_with_db
    src = mount.parent / "newsong.mp3"
    src.write_bytes(b"ID3-FAKE-AUDIO" * 100)

    new = TrackInfo(title="New Song", location="", artist="New Artist", filetype="mp3", length=180000)
    new.source_path = str(src)

    res = sync_media_to_ipod(mount, [new], device_info=dev, consent_ack=True)
    assert res.success is True

    # El audio se copió a Music/Fxx/.
    copied = list((mount / "iPod_Control" / "Music").rglob("*.mp3"))
    assert any(p.read_bytes() == src.read_bytes() for p in copied)

    # La base reescrita tiene ambas pistas (existente + nueva).
    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    titles = {t.get("Title") for t in lib["mhlt"]}
    assert "New Song" in titles and "Existing" in titles


def test_sync_media_sin_source_path_falla(ipod_with_db):
    mount, dev = ipod_with_db
    with pytest.raises(ValueError):
        sync_media_to_ipod(mount, [TrackInfo(title="X", location="")], device_info=dev, consent_ack=True)


def test_sync_media_consent_requerido_no_copia(ipod_with_db, tmp_path):
    mount, dev = ipod_with_db
    src = tmp_path / "s.mp3"
    src.write_bytes(b"AUDIO")
    new = TrackInfo(title="Y", location="", filetype="mp3")
    new.source_path = str(src)
    from cicada.ipod.db.coordinator.consent import ConsentRequiredError
    with pytest.raises(ConsentRequiredError):
        sync_media_to_ipod(mount, [new], device_info=dev, consent_ack=False)
    # No debe haber quedado audio copiado (se abortó antes de copiar).
    assert not list((mount / "iPod_Control" / "Music").rglob("*.mp3"))


def test_sync_media_preserva_y_crea_playlists(ipod_with_db):
    mount, dev = ipod_with_db
    src = mount.parent / "plsong.mp3"
    src.write_bytes(b"AUDIO" * 40)
    new = TrackInfo(title="Song Enviada", location="", filetype="mp3")
    new.source_path = str(src)

    res = sync_media_to_ipod(
        mount, [new], device_info=dev, consent_ack=True,
        playlists=[{"name": "Enviada", "source_paths": [str(src)]}],
    )
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    names = {p.get("Title") for p in lib["mhlp"]}
    assert "Mi Playlist" in names   # existente preservada (antes se borraba)
    assert "Enviada" in names       # nueva creada

    mi = next(p for p in lib["mhlp"] if p.get("Title") == "Mi Playlist")
    assert len(mi.get("items", [])) == 1   # su pista se preservó (no quedó vacía)
    enviada = next(p for p in lib["mhlp"] if p.get("Title") == "Enviada")
    assert len(enviada.get("items", [])) == 1   # contiene la pista enviada


def test_sync_media_playlist_con_paths_desincronizados_no_desaparece(ipod_with_db):
    # Regresión: si el frontend envía una playlist referenciando source_paths que
    # ya no vienen en la lista de pistas nuevas (p.ej. el usuario quitó esa pista
    # del carrito), la playlist NO debe desaparecer en silencio.
    mount, dev = ipod_with_db
    src = mount.parent / "otracosa.mp3"
    src.write_bytes(b"AUDIO" * 40)
    new = TrackInfo(title="Otra", location="", filetype="mp3")
    new.source_path = str(src)

    res = sync_media_to_ipod(
        mount, [new], device_info=dev, consent_ack=True,
        playlists=[{"name": "Desincronizada", "source_paths": ["/no/existe/en/las/nuevas.mp3"]}],
    )
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    names = {p.get("Title") for p in lib["mhlp"]}
    assert "Desincronizada" in names   # se crea (aunque vacía), nunca se descarta


def test_sync_media_sin_playlists_preserva_existentes(ipod_with_db):
    # Aunque no se envíen playlists, un sync normal NO debe borrar las de usuario.
    mount, dev = ipod_with_db
    src = mount.parent / "x.mp3"
    src.write_bytes(b"A" * 30)
    new = TrackInfo(title="X", location="", filetype="mp3")
    new.source_path = str(src)
    res = sync_media_to_ipod(mount, [new], device_info=dev, consent_ack=True)
    assert res.success is True
    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    assert "Mi Playlist" in {p.get("Title") for p in lib["mhlp"]}
