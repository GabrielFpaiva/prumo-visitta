"""Structure-from-motion com pycolmap e o veredito "a captura serve ou não"."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import EngineError

MIN_REGISTERED_RATIO = 0.6
EXHAUSTIVE_MAX_IMAGES = 150
SEQUENTIAL_OVERLAP = 20


@dataclass(frozen=True)
class ModelSummary:
    index: int
    registered: int


class ColmapBackend(Protocol):
    def extract(self, database: Path, images: Path) -> None: ...
    def match(self, database: Path, *, sequential: bool) -> None: ...
    def map(self, database: Path, images: Path, output: Path) -> list[ModelSummary]: ...


class PycolmapBackend:
    """Uma câmera por subpasta (fotos, video0, video1…), modelo OPENCV (lente de celular)."""

    def __init__(self, camera_model: str = "OPENCV") -> None:
        self.camera_model = camera_model

    def extract(self, database: Path, images: Path) -> None:
        import pycolmap

        reader = pycolmap.ImageReaderOptions()
        reader.camera_model = self.camera_model
        pycolmap.extract_features(
            database, images, camera_mode=pycolmap.CameraMode.PER_FOLDER, reader_options=reader
        )

    def match(self, database: Path, *, sequential: bool) -> None:
        import pycolmap

        if sequential:
            pairing = pycolmap.SequentialPairingOptions()
            pairing.overlap = SEQUENTIAL_OVERLAP
            pycolmap.match_sequential(database, pairing_options=pairing)
        else:
            pycolmap.match_exhaustive(database)

    def map(self, database: Path, images: Path, output: Path) -> list[ModelSummary]:
        import pycolmap

        reconstructions = pycolmap.incremental_mapping(database, images, output)
        summaries = []
        for index, rec in reconstructions.items():
            model_dir = output / str(index)
            model_dir.mkdir(parents=True, exist_ok=True)
            rec.write(model_dir)
            summaries.append(ModelSummary(index=index, registered=rec.num_reg_images()))
        return summaries


@dataclass(frozen=True)
class SfmResult:
    registered: int
    total: int
    model_dir: Path

    @property
    def ratio(self) -> float:
        return self.registered / self.total if self.total else 0.0


def run_sfm(images: Path, work: Path, backend: ColmapBackend) -> SfmResult:
    total = len(list(images.rglob("*.jpg")))
    work.mkdir(parents=True, exist_ok=True)
    database = work / "database.db"
    output = work / "sparse_all"
    output.mkdir(parents=True, exist_ok=True)

    backend.extract(database, images)
    backend.match(database, sequential=total > EXHAUSTIVE_MAX_IMAGES)
    models = backend.map(database, images, output)
    if not models:
        raise EngineError("CAPTURE_INSUFFICIENT", f"0/{total} imagens registradas")

    best = max(models, key=lambda m: m.registered)
    result = SfmResult(registered=best.registered, total=total, model_dir=output / str(best.index))
    if result.ratio < MIN_REGISTERED_RATIO:
        raise EngineError("CAPTURE_INSUFFICIENT", f"{best.registered}/{total} imagens registradas")
    return result
