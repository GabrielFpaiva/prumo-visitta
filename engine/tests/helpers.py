from pathlib import Path

import numpy as np
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

EXIF_ORIENTATION = 0x0112
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 36867


def make_photo(path: Path, size=(800, 600), *, orientation=None, taken=None, seed=0) -> Path:
    """Imagem com ruído (textura) e EXIF opcional, salva no formato da extensão."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(pixels)
    exif = Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    if taken is not None:
        exif.get_ifd(EXIF_IFD)[DATETIME_ORIGINAL] = taken
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, exif=exif)
    return path
