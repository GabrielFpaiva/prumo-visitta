import numpy as np
from PIL import Image

from helpers import make_photo
from visitta_engine.inputs import normalize_photos


def size_of(path):
    with Image.open(path) as im:
        return im.size


def pixels(path):
    with Image.open(path) as im:
        return np.asarray(im).astype(int)


def test_downscales_to_max_side(tmp_path):
    src = make_photo(tmp_path / "src" / "big.jpg", size=(4000, 3000))
    result = normalize_photos([src], tmp_path / "out")
    assert [p.name for p in result.paths] == ["foto_0000.jpg"]
    assert size_of(result.paths[0]) == (1600, 1200)


def test_small_photo_is_not_upscaled(tmp_path):
    src = make_photo(tmp_path / "src" / "small.png", size=(640, 480))
    result = normalize_photos([src], tmp_path / "out")
    assert size_of(result.paths[0]) == (640, 480)


def test_applies_exif_rotation(tmp_path):
    # orientação 6 = girar 90° no sentido horário para exibir
    src = make_photo(tmp_path / "src" / "deitada.jpg", size=(800, 400), orientation=6)
    result = normalize_photos([src], tmp_path / "out")
    assert size_of(result.paths[0]) == (400, 800)


def test_converts_heic(tmp_path):
    src = make_photo(tmp_path / "src" / "IMG_0001.heic", size=(800, 600))
    result = normalize_photos([src], tmp_path / "out")
    with Image.open(result.paths[0]) as im:
        assert im.format == "JPEG"
        assert im.size == (800, 600)


def test_orders_by_capture_time_then_name(tmp_path):
    late = make_photo(tmp_path / "src" / "a.jpg", taken="2026:10:01 10:05:00", seed=1)
    early = make_photo(tmp_path / "src" / "b.jpg", taken="2026:10:01 10:00:00", seed=2)
    result = normalize_photos([late, early], tmp_path / "out")
    first = pixels(result.paths[0])
    # JPEG recomprimido não preserva pixel exato; a primeira saída fica perto da foto mais antiga
    assert abs(first - pixels(early)).mean() < abs(first - pixels(late)).mean()


def test_skips_unreadable_photo(tmp_path):
    good = make_photo(tmp_path / "src" / "ok.jpg")
    bad = tmp_path / "src" / "quebrada.jpg"
    bad.write_bytes(b"isto nao e uma imagem")
    result = normalize_photos([good, bad], tmp_path / "out")
    assert len(result.paths) == 1
    assert result.skipped == 1


def test_truncated_heic_is_skipped(tmp_path):
    good = make_photo(tmp_path / "src" / "IMG_0001.heic")
    data = make_photo(tmp_path / "src" / "IMG_0002.heic", seed=3).read_bytes()
    cut = tmp_path / "src" / "IMG_0002.heic"
    cut.write_bytes(data[: len(data) // 2])
    result = normalize_photos([good, cut], tmp_path / "out")
    assert len(result.paths) == 1
    assert result.skipped == 1


def test_groups_photos_by_size_so_each_folder_is_one_camera(tmp_path):
    wide = make_photo(tmp_path / "src" / "a.jpg", size=(640, 480))
    tall = make_photo(tmp_path / "src" / "b.jpg", size=(640, 480), orientation=6)
    result = normalize_photos([wide, tall], tmp_path / "out")
    folders = {p.parent.name: size_of(p) for p in result.paths}
    assert folders == {"640x480": (640, 480), "480x640": (480, 640)}
    assert all(p.parent.parent == tmp_path / "out" for p in result.paths)


def test_oversized_photo_is_skipped(tmp_path, monkeypatch):
    # Pillow levanta DecompressionBombError (não é OSError) acima de 2× MAX_IMAGE_PIXELS
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    good = make_photo(tmp_path / "src" / "ok.jpg", size=(40, 20))
    huge = make_photo(tmp_path / "src" / "pano.jpg", size=(800, 600))
    result = normalize_photos([good, huge], tmp_path / "out")
    assert len(result.paths) == 1
    assert result.skipped == 1
