"""Vídeo → quadros nítidos. Amostra a 4 fps e fica com o mais nítido de cada janela."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

import cv2

from .inputs import MAX_SIDE
from .runner import Runner


def laplacian_variance(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def select_sharpest(scores: Sequence[float], window: int, cap: int) -> list[int]:
    if cap <= 0 or not scores:
        return []
    picks = [
        max(range(start, min(start + window, len(scores))), key=lambda i: scores[i])
        for start in range(0, len(scores), window)
    ]
    if len(picks) > cap:
        step = len(picks) / cap
        picks = [picks[int(k * step)] for k in range(cap)]
    return picks


def extract_video_frames(
    video: Path,
    out_dir: Path,
    runner: Runner,
    *,
    cap: int,
    sample_fps: int = 4,
    window: int = 2,
    max_side: int = MAX_SIDE,
) -> list[Path]:
    raw = out_dir.parent / f"_raw_{out_dir.name}"
    raw.mkdir(parents=True, exist_ok=True)
    try:
        scale = (
            f"scale='min({max_side},iw)':'min({max_side},ih)'"
            ":force_original_aspect_ratio=decrease:force_divisible_by=2"
        )
        runner.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
            "-vf", f"fps={sample_fps},{scale}", "-q:v", "2", str(raw / "f_%05d.jpg"),
        ])
        candidates = sorted(raw.glob("f_*.jpg"))
        picks = select_sharpest([laplacian_variance(p) for p in candidates], window, cap)
        out_dir.mkdir(parents=True, exist_ok=True)
        result = []
        for n, index in enumerate(picks):
            dest = out_dir / f"q_{n:04d}.jpg"
            shutil.move(candidates[index], dest)
            result.append(dest)
        return result
    finally:
        shutil.rmtree(raw, ignore_errors=True)
