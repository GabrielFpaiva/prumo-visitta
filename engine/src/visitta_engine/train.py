"""Treino com o simple_trainer do gsplat e compressão para .sog (web)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import EngineError
from .runner import Runner


@dataclass(frozen=True)
class Preset:
    name: str
    max_steps: int
    strategy: str


PRESETS = {
    "rapida": Preset("rapida", 7_000, "default"),
    "boa": Preset("boa", 30_000, "default"),
    "alta": Preset("alta", 30_000, "mcmc"),
}

_PLY_STEP = re.compile(r"point_cloud_(\d+)\.ply$")
_VAL_STEP = re.compile(r"val_step(\d+)\.json$")


def train_command(preset: Preset, data_dir: Path, result_dir: Path, *, python: str, trainer: str) -> list[str]:
    steps = str(preset.max_steps)
    return [
        python, trainer, preset.strategy,
        "--data_dir", str(data_dir),
        "--data_factor", "1",
        "--result_dir", str(result_dir),
        "--max_steps", steps,
        "--save_steps", steps,
        "--eval_steps", steps,
        "--ply_steps", steps,
        "--save_ply",
        "--disable_viewer",
    ]


def find_final_ply(result_dir: Path) -> Path:
    found = [(int(m.group(1)), p) for p in (result_dir / "ply").glob("point_cloud_*.ply") if (m := _PLY_STEP.search(p.name))]
    if not found:
        raise EngineError("ENGINE_ERROR", "treino terminou sem PLY")
    return max(found)[1]


def count_gaussians(ply: Path) -> int:
    with ply.open("rb") as fh:
        for raw in fh:
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("element vertex "):
                return int(line.split()[-1])
            if line == "end_header":
                break
    raise EngineError("ENGINE_ERROR", "PLY sem element vertex")


def read_psnr(result_dir: Path) -> float | None:
    found = [(int(m.group(1)), p) for p in (result_dir / "stats").glob("val_step*.json") if (m := _VAL_STEP.search(p.name))]
    if not found:
        return None
    value = json.loads(max(found)[1].read_text()).get("psnr")
    return float(value) if value is not None else None


def compress(ply: Path, out_sog: Path, runner: Runner, *, viewer_html: Path | None = None) -> None:
    runner.run(["splat-transform", str(ply), "--filter-nan", str(out_sog)])
    if viewer_html is not None:
        runner.run(["splat-transform", str(out_sog), str(viewer_html)])
