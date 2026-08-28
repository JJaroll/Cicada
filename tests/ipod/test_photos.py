"""Tests para el módulo de Fotos del iPod (cicada/ipod/photos.py y endpoints en api.py)."""
from __future__ import annotations

import io
from pathlib import Path
from PIL import Image
import httpx
import pytest

from cicada.core.main import app
from cicada.ipod.device.device_info import DeviceInfo
from cicada.ipod.photos import (
    get_photo_preview_bytes,
    get_photo_thumbnail_bytes,
    resolve_photo_raw_file,
    scan_ipod_photos,
)


@pytest.fixture
def fake_ipod_photos_tree(tmp_path: Path) -> Path:
    """Crea una estructura mock de iPod con directorio Photos."""
    photos_dir = tmp_path / "Photos" / "Full Resolution" / "2026" / "08"
    photos_dir.mkdir(parents=True, exist_ok=True)

    # Crear 2 imágenes sintéticas
    img1 = Image.new("RGB", (800, 600), color=(255, 0, 0))
    img1.save(photos_dir / "test1.jpg", format="JPEG")

    img2 = Image.new("RGB", (1024, 768), color=(0, 255, 0))
    img2.save(photos_dir / "test2.jpg", format="JPEG")

    # Archivo no imagen (debe ignorarse)
    (photos_dir / "ignore.txt").write_text("no es imagen")
    (photos_dir / "._test1.jpg").write_bytes(b"appledouble")

    return tmp_path


def test_scan_ipod_photos(fake_ipod_photos_tree: Path):
    photos = scan_ipod_photos(fake_ipod_photos_tree)
    assert len(photos) == 2
    filenames = {p.filename for p in photos}
    assert filenames == {"test1.jpg", "test2.jpg"}

    p1 = next(p for p in photos if p.filename == "test1.jpg")
    assert p1.size_bytes > 0
    assert "2026/08/test1.jpg" in p1.rel_path


def test_get_photo_thumbnail_bytes(fake_ipod_photos_tree: Path):
    thumb = get_photo_thumbnail_bytes(fake_ipod_photos_tree, "2026/08/test1.jpg", max_size=(200, 200))
    assert thumb is not None
    assert isinstance(thumb, bytes)

    # Verificar que el thumbnail sea una imagen válida y respete el max_size
    img = Image.open(io.BytesIO(thumb))
    assert img.format == "JPEG"
    assert img.width <= 200
    assert img.height <= 200


def test_get_photo_preview_bytes(fake_ipod_photos_tree: Path):
    prev = get_photo_preview_bytes(fake_ipod_photos_tree, "2026/08/test1.jpg", max_size=(600, 600))
    assert prev is not None
    assert isinstance(prev, bytes)

    img = Image.open(io.BytesIO(prev))
    assert img.format == "JPEG"
    assert img.width <= 600
    assert img.height <= 600


def test_get_photo_thumbnail_path_traversal(fake_ipod_photos_tree: Path):
    # Intentar escape con path traversal
    thumb = get_photo_thumbnail_bytes(fake_ipod_photos_tree, "../../etc/passwd")
    assert thumb is None


def test_resolve_photo_raw_file(fake_ipod_photos_tree: Path):
    raw = resolve_photo_raw_file(fake_ipod_photos_tree, "2026/08/test1.jpg")
    assert raw is not None
    assert raw.is_file()

    bad = resolve_photo_raw_file(fake_ipod_photos_tree, "../../secret.txt")
    assert bad is None


@pytest.mark.asyncio
async def test_api_photos_endpoints(monkeypatch, fake_ipod_photos_tree: Path):
    mock_dev = DeviceInfo(
        mount=fake_ipod_photos_tree,
        firewire_guid="000A27002484DDFB",
        guid_provenance="disk",
    )
    monkeypatch.setattr("cicada.ipod.api.resolve_mount", lambda: fake_ipod_photos_tree)
    monkeypatch.setattr("cicada.ipod.api.read_device_info", lambda m: mock_dev)
    monkeypatch.setattr("cicada.ipod.photos._get_photos_dir", lambda m: fake_ipod_photos_tree / "Photos")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. GET /api/ipod/photos
        res = await client.get("/api/ipod/photos")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 2
        assert len(data["photos"]) == 2
        assert "thumb_url" in data["photos"][0]
        assert "preview_url" in data["photos"][0]
        assert "raw_url" in data["photos"][0]

        # 2. GET /api/ipod/photos/thumbnail
        rel_path = data["photos"][0]["rel_path"]
        res_thumb = await client.get(f"/api/ipod/photos/thumbnail?path={rel_path}")
        assert res_thumb.status_code == 200
        assert res_thumb.headers["content-type"] == "image/jpeg"

        # 3. GET /api/ipod/photos/preview
        res_prev = await client.get(f"/api/ipod/photos/preview?path={rel_path}")
        assert res_prev.status_code == 200
        assert res_prev.headers["content-type"] == "image/jpeg"

        # 4. GET /api/ipod/photos/raw
        res_raw = await client.get(f"/api/ipod/photos/raw?path={rel_path}")
        assert res_raw.status_code == 200
        assert res_raw.headers["content-type"] == "image/jpeg"
