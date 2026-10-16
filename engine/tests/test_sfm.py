import importlib.util

import pytest

from helpers import make_photo
from visitta_engine.errors import EngineError
from visitta_engine.sfm import ModelSummary, PycolmapBackend, run_sfm


class FakeBackend:
    def __init__(self, models):
        self.models = models
        self.sequential = None

    def extract(self, database, images):
        database.write_bytes(b"db")

    def match(self, database, *, sequential):
        self.sequential = sequential

    def map(self, database, images, output):
        for m in self.models:
            (output / str(m.index)).mkdir(parents=True)
            (output / str(m.index) / "images.bin").write_bytes(b"x")
        return self.models


def make_images(root, n):
    folder = root / "images" / "fotos"
    folder.mkdir(parents=True)
    for i in range(n):
        (folder / f"foto_{i:04d}.jpg").write_bytes(b"jpg")
    return root / "images"


def test_picks_largest_model(tmp_path):
    images = make_images(tmp_path, 100)
    backend = FakeBackend([ModelSummary(0, 30), ModelSummary(1, 70)])
    result = run_sfm(images, tmp_path / "colmap", backend)
    assert result.registered == 70
    assert result.total == 100
    assert result.model_dir == tmp_path / "colmap" / "sparse_all" / "1"
    assert result.ratio == pytest.approx(0.7)


def test_split_scene_counts_ratio_against_total(tmp_path):
    images = make_images(tmp_path, 100)
    backend = FakeBackend([ModelSummary(0, 45), ModelSummary(1, 50)])
    with pytest.raises(EngineError) as exc:
        run_sfm(images, tmp_path / "colmap", backend)
    assert exc.value.code == "CAPTURE_INSUFFICIENT"
    assert "50/100" in exc.value.detail


def test_no_model_is_capture_insufficient(tmp_path):
    images = make_images(tmp_path, 50)
    with pytest.raises(EngineError) as exc:
        run_sfm(images, tmp_path / "colmap", FakeBackend([]))
    assert exc.value.code == "CAPTURE_INSUFFICIENT"


def test_sequential_matching_above_threshold(tmp_path):
    small = FakeBackend([ModelSummary(0, 150)])
    run_sfm(make_images(tmp_path / "a", 150), tmp_path / "a" / "colmap", small)
    assert small.sequential is False
    big = FakeBackend([ModelSummary(0, 151)])
    run_sfm(make_images(tmp_path / "b", 151), tmp_path / "b" / "colmap", big)
    assert big.sequential is True


@pytest.mark.skipif(importlib.util.find_spec("pycolmap") is None, reason="pycolmap ausente")
def test_pycolmap_backend_runs_on_cpu(tmp_path):
    """Confere as assinaturas reais do pycolmap; com imagens aleatórias não sai modelo."""
    images = tmp_path / "images"
    for i in range(3):
        make_photo(images / "fotos" / f"foto_{i:04d}.jpg", size=(320, 240), seed=i)
    backend = PycolmapBackend()
    db = tmp_path / "database.db"
    backend.extract(db, images)
    backend.match(db, sequential=False)
    out = tmp_path / "sparse_all"
    out.mkdir()
    models = backend.map(db, images, out)
    assert isinstance(models, list)
