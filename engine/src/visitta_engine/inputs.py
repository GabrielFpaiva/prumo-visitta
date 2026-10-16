"""Fotos do corretor → JPEGs em pé, no máximo 1600 px, na ordem em que foram tiradas."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_SIDE = 1600
_EXIF_IFD = 0x8769
_DATETIME_ORIGINAL = 36867


# ValueError: pillow-heif com HEIC cortado; DecompressionBombError não herda de OSError.
_UNREADABLE = (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)


@dataclass(frozen=True)
class NormalizedPhotos:
    paths: list[Path]
    skipped: int


def _capture_time(path: Path) -> str:
    try:
        with Image.open(path) as im:
            value = im.getexif().get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL, "")
    except _UNREADABLE:
        return ""
    return value if isinstance(value, str) else ""


def normalize_photos(sources: Sequence[Path], out_dir: Path, max_side: int = MAX_SIDE) -> NormalizedPhotos:
    """Grava em `out_dir/<L>x<A>/`: o COLMAP (PER_FOLDER) dá uma câmera por pasta e descarta
    foto de tamanho diferente da primeira, então retrato e paisagem precisam de pastas próprias."""
    ordered = sorted(sources, key=lambda p: (_capture_time(p), p.name))
    paths: list[Path] = []
    skipped = 0
    for src in ordered:
        try:
            with Image.open(src) as im:
                upright = ImageOps.exif_transpose(im).convert("RGB")
        except _UNREADABLE:
            skipped += 1
            continue
        upright.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        folder = out_dir / f"{upright.width}x{upright.height}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"foto_{len(paths):04d}.jpg"
        upright.save(dest, "JPEG", quality=92)
        paths.append(dest)
    return NormalizedPhotos(paths=paths, skipped=skipped)
