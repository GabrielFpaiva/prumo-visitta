"""CLI da instância: `python -m visitta_engine run --manifest-url URL`."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .errors import EngineError
from .manifest import parse_manifest
from .pipeline import Deps, run_job
from .runner import SubprocessRunner
from .sfm import PycolmapBackend
from .transport import Notifier, download


def _gpu_name() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None


def _load_manifest(args: argparse.Namespace, work: Path) -> dict:
    if args.manifest_file:
        return _parse_json(Path(args.manifest_file))
    url = args.manifest_url or os.environ.get("VISITTA_MANIFEST_URL")
    if not url:
        raise EngineError("MANIFEST_INVALID", "passe --manifest-url, --manifest-file ou VISITTA_MANIFEST_URL")
    dest = work / "manifest.json"
    download(url, dest, backoff=1.0)
    return _parse_json(dest)


def _parse_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise EngineError("MANIFEST_INVALID", f"JSON inválido: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="visitta_engine", description="Motor do Prumo Visitta")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="processa um job descrito por um manifesto")
    run.add_argument("--manifest-url")
    run.add_argument("--manifest-file")
    run.add_argument("--workdir", default="/work")
    args = parser.parse_args(argv)

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    try:
        manifest = parse_manifest(_load_manifest(args, work))
    except EngineError as err:
        print(f"falhou: {err}", file=sys.stderr)
        return err.exit_code

    deps = Deps(
        runner=SubprocessRunner(),
        colmap=PycolmapBackend(),
        notifier=Notifier(manifest.callback, manifest.job_id),
        trainer_python=os.environ.get("VISITTA_TRAINER_PYTHON", "/opt/train/bin/python"),
        trainer_script=os.environ.get("VISITTA_TRAINER_SCRIPT", "/opt/gsplat/examples/simple_trainer.py"),
        gpu=_gpu_name(),
    )
    return run_job(manifest, work, deps)


if __name__ == "__main__":
    sys.exit(main())
