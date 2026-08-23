"""Round-trip binario de los chunks de ArtworkDB (Fase 4, Etapa 4c)."""
from cicada.ipod.db.artwork.chunks import (
    build_artworkdb,
    ithmb_filename,
    read_artworkdb,
    write_mhfd,
    write_mhii,
)
from cicada.ipod.db.artwork.types import EncodedFormatPayload


def _payload(width=4, height=4, hpad=0, vpad=0) -> EncodedFormatPayload:
    stride = width + hpad
    data = bytes(range(256))[: stride * height * 2].ljust(stride * height * 2, b"\x00")
    return EncodedFormatPayload(
        data=data, width=width, height=height, size=len(data),
        stride_pixels=stride, hpad=hpad, vpad=vpad, pixel_format="RGB565_LE",
    )


def test_ithmb_filename_format():
    assert ithmb_filename(1010) == "F1010_1.ithmb"
    assert ithmb_filename(1010, index=2) == "F1010_2.ithmb"


class TestMhiiRoundTrip:
    def test_single_format_fields_survive(self):
        payload = _payload(width=10, height=5, hpad=2)
        blob = write_mhii(
            img_id=101, db_track_id=999_888_777, src_img_size=54321,
            formats={1010: payload}, offsets={1010: 4096},
            filenames={1010: "F1010_1.ithmb"},
        )
        db = build_artworkdb([blob], format_ids=[1010], image_sizes={1010: payload.size}, next_img_id=102)
        entries = read_artworkdb(db)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.img_id == 101
        assert entry.db_track_id == 999_888_777
        assert entry.src_img_size == 54321
        assert set(entry.formats.keys()) == {1010}

        ref = entry.formats[1010]
        assert ref.ithmb_offset == 4096
        assert ref.size == payload.size
        assert ref.width == 10
        assert ref.height == 5
        assert ref.hpad == 2
        assert ref.vpad == 0
        assert ref.filename == "F1010_1.ithmb"

    def test_multiple_formats_per_entry(self):
        p1 = _payload(width=240, height=240)
        p2 = _payload(width=50, height=50)
        blob = write_mhii(
            img_id=5, db_track_id=1, src_img_size=1000,
            formats={1010: p1, 1013: p2},
            offsets={1010: 0, 1013: 999},
            filenames={1010: "F1010_1.ithmb", 1013: "F1013_1.ithmb"},
        )
        db = build_artworkdb(
            [blob], format_ids=[1010, 1013],
            image_sizes={1010: p1.size, 1013: p2.size}, next_img_id=6,
        )
        entries = read_artworkdb(db)
        assert len(entries) == 1
        assert set(entries[0].formats.keys()) == {1010, 1013}
        assert entries[0].formats[1010].ithmb_offset == 0
        assert entries[0].formats[1013].ithmb_offset == 999

    def test_large_db_track_id_survives_u64(self):
        # song_id/db_track_id se empaqueta como u64 — verificar que no se
        # trunca a 32 bits con IDs grandes (Cicada usa IDs de 64 bits).
        big_id = 0xFFFFFFFF12345678
        payload = _payload()
        blob = write_mhii(
            img_id=1, db_track_id=big_id, src_img_size=1,
            formats={1010: payload}, offsets={1010: 0},
            filenames={1010: "F1010_1.ithmb"},
        )
        db = build_artworkdb([blob], [1010], {1010: payload.size}, next_img_id=2)
        entries = read_artworkdb(db)
        assert entries[0].db_track_id == big_id


class TestMultipleEntries:
    def test_preserves_order_and_distinct_ids(self):
        payload = _payload()
        blobs = [
            write_mhii(
                img_id=100 + i, db_track_id=i * 10, src_img_size=i,
                formats={1010: payload}, offsets={1010: i * payload.size},
                filenames={1010: "F1010_1.ithmb"},
            )
            for i in range(5)
        ]
        db = build_artworkdb(blobs, [1010], {1010: payload.size}, next_img_id=105)
        entries = read_artworkdb(db)
        assert [e.img_id for e in entries] == [100, 101, 102, 103, 104]
        assert [e.db_track_id for e in entries] == [0, 10, 20, 30, 40]
        assert [e.formats[1010].ithmb_offset for e in entries] == [0, payload.size, 2 * payload.size, 3 * payload.size, 4 * payload.size]


def test_build_artworkdb_empty_is_still_valid():
    db = build_artworkdb([], format_ids=[1010], image_sizes={1010: 0}, next_img_id=100)
    entries = read_artworkdb(db)
    assert entries == []
    assert db[:4] == b"mhfd"


def test_build_artworkdb_has_three_datasets():
    db = build_artworkdb([], [1010], {1010: 0}, next_img_id=100)
    # 3 MHSD hijos: IMAGE_LIST, PHOTO_ALBUM_LIST, FILE_LIST.
    import struct
    num_datasets = struct.unpack_from("<I", db, 20)[0]
    assert num_datasets == 3


def test_write_mhfd_offset_48_en_cero():
    import struct
    blob = write_mhfd([], next_img_id=100)
    assert struct.unpack_from("<I", blob, 48)[0] == 0
