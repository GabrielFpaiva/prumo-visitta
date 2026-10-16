"""Relatório de medição de um job: é o que o spike compara entre imóveis e presets."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Report:
    job_id: str
    preset: str
    stages: dict[str, float] = field(default_factory=dict)
    photos: int = 0
    videos: int = 0
    skipped_photos: int = 0
    skipped_videos: int = 0
    images_total: int = 0
    registered: int = 0
    gaussians: int = 0
    splat_bytes: int = 0
    psnr: float | None = None
    gpu: str | None = None
    error: str | None = None

    @contextmanager
    def stage(self, name: str, on_enter: Callable[[str], None] | None = None) -> Iterator[None]:
        if on_enter is not None:
            on_enter(name)
        start = time.monotonic()
        try:
            yield
        finally:
            self.stages[name] = round(time.monotonic() - start, 2)

    def to_json(self) -> bytes:
        data = {
            "jobId": self.job_id,
            "preset": self.preset,
            "stages": self.stages,
            "totalSeconds": round(sum(self.stages.values()), 2),
            "photos": self.photos,
            "videos": self.videos,
            "skippedPhotos": self.skipped_photos,
            "skippedVideos": self.skipped_videos,
            "imagesTotal": self.images_total,
            "registered": self.registered,
            "gaussians": self.gaussians,
            "splatBytes": self.splat_bytes,
            "psnr": self.psnr,
            "gpu": self.gpu,
            "error": self.error,
        }
        return json.dumps(data, ensure_ascii=False, indent=2).encode()
