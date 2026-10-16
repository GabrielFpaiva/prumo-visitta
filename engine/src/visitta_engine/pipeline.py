"""Orquestra os estágios de um job e transforma qualquer falha num código do spec §8."""

from __future__ import annotations

import errno
import shutil
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from .errors import EngineError, classify_command_failure
from .frames import extract_video_frames
from .inputs import normalize_photos
from .manifest import Manifest
from .report import Report
from .runner import CommandFailed, Runner
from .sfm import ColmapBackend, run_sfm
from .train import PRESETS, compress, count_gaussians, find_final_ply, read_psnr, train_command
from .transport import Notifier, download, upload

MIN_IMAGES = 40
MAX_IMAGES = 300


@dataclass
class Deps:
    runner: Runner
    colmap: ColmapBackend
    notifier: Notifier
    trainer_python: str
    trainer_script: str
    gpu: str | None = None
    transfer_backoff: float = 2.0


def _set_stage(deps: Deps):
    def enter(name: str) -> None:
        deps.notifier.stage = name
        deps.notifier.send("progresso")
    return enter


def run_pipeline(manifest: Manifest, work: Path, deps: Deps, report: Report) -> None:
    enter = _set_stage(deps)
    data = work / "data"
    images = data / "images"

    with report.stage("baixando", enter):
        local = []
        for i, item in enumerate(manifest.inputs):
            dest = work / "in" / f"{i:03d}{item.ext}"
            download(item.url, dest, backoff=deps.transfer_backoff)
            local.append((item.kind, dest))

    with report.stage("quadros", enter):
        photos = [p for kind, p in local if kind == "photo"]
        videos = [p for kind, p in local if kind == "video"]
        report.photos, report.videos = len(photos), len(videos)
        normalized = normalize_photos(photos, images / "fotos") if photos else None
        if normalized is not None:
            report.skipped_photos = normalized.skipped
        n_photos = len(_keep_evenly(normalized.paths, MAX_IMAGES)) if normalized else 0
        remaining = max(0, MAX_IMAGES - n_photos)
        per_video = remaining // len(videos) if videos else 0
        n_frames = 0
        for j, video in enumerate(videos):
            try:
                frames = extract_video_frames(video, images / f"video{j}", deps.runner, cap=per_video)
            except CommandFailed as exc:
                if not _is_unreadable_video(exc):
                    raise
                report.skipped_videos += 1
                continue
            n_frames += len(frames)
        report.images_total = n_photos + n_frames
        if report.images_total < MIN_IMAGES:
            raise EngineError("CAPTURE_TOO_FEW", f"{report.images_total} imagens, mínimo {MIN_IMAGES}")

    with report.stage("colmap", enter):
        sfm = run_sfm(images, work / "colmap", deps.colmap)
        report.registered = sfm.registered
        shutil.copytree(sfm.model_dir, data / "sparse" / "0")

    preset = PRESETS[manifest.preset]
    result = work / "result"
    with report.stage("treino", enter):
        deps.runner.run(
            train_command(preset, data, result, python=deps.trainer_python, trainer=deps.trainer_script),
            log=work / "train.log",
        )

    out = work / "out"
    out.mkdir(parents=True, exist_ok=True)
    sog = out / "tour.sog"
    viewer = out / "viewer.html" if manifest.outputs.viewer_url else None
    with report.stage("compressao", enter):
        ply = find_final_ply(result)
        report.gaussians = count_gaussians(ply)
        report.psnr = read_psnr(result)
        compress(ply, sog, deps.runner, viewer_html=viewer)
        report.splat_bytes = sog.stat().st_size

    with report.stage("enviando", enter):
        upload(sog, manifest.outputs.splat_url, "application/octet-stream", backoff=deps.transfer_backoff)
        if viewer is not None and manifest.outputs.viewer_url:
            upload(viewer, manifest.outputs.viewer_url, "text/html; charset=utf-8", backoff=deps.transfer_backoff)


def _keep_evenly(paths: list[Path], limit: int) -> list[Path]:
    """Apaga o excesso espalhado pela captura, não só o fim (que seria o último cômodo)."""
    if len(paths) <= limit:
        return paths
    step = len(paths) / limit
    keep = {int(k * step) for k in range(limit)}
    for i, path in enumerate(paths):
        if i not in keep:
            path.unlink()
    return [p for i, p in enumerate(paths) if i in keep]


def _is_unreadable_video(exc: CommandFailed) -> bool:
    """Só o ffmpeg recusando o arquivo conta como vídeo ruim. Binário ausente (127), processo
    morto por sinal (< 0), disco cheio ou GPU quebrada não são culpa da captura."""
    if exc.returncode <= 0 or exc.returncode == 127:
        return False
    return classify_command_failure(exc.stderr_tail) == "ENGINE_ERROR"


def _as_engine_error(exc: BaseException) -> EngineError:
    if isinstance(exc, EngineError):
        return exc
    if isinstance(exc, CommandFailed):
        return EngineError(classify_command_failure(exc.stderr_tail), exc.stderr_tail[-500:])
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return EngineError("HOST_DISK", str(exc))
    detail = f"{type(exc).__name__}: {exc}"
    # pycolmap roda no processo: erro de CUDA dele chega como RuntimeError, sem passar pelo Runner
    return EngineError(classify_command_failure(detail), detail)


def _upload_report(manifest: Manifest, work: Path, report: Report, deps: Deps) -> None:
    """Nunca levanta: o evento final (concluiu/falhou) e o exit code vêm depois e importam mais."""
    try:
        path = work / "report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(report.to_json())
        upload(path, manifest.outputs.report_url, "application/json", backoff=deps.transfer_backoff)
    except Exception as exc:  # noqa: BLE001
        print(f"relatório não subiu: {exc!r}", file=sys.stderr)


def run_job(manifest: Manifest, work: Path, deps: Deps) -> int:
    report = Report(job_id=manifest.job_id, preset=manifest.preset, gpu=deps.gpu)
    deps.notifier.send("iniciou")
    err: EngineError | None = None
    # O relatório pode levar minutos com retentativas: sem heartbeat nesse trecho, o orquestrador
    # acha que o host morreu. O evento final sai depois, para nenhum `progresso` chegar atrasado.
    with deps.notifier.heartbeat():
        try:
            run_pipeline(manifest, work, deps, report)
        except Exception as exc:  # noqa: BLE001 — toda falha vira código do spec
            err = _as_engine_error(exc)
            if err.code == "ENGINE_ERROR":
                traceback.print_exc()
            report.error = err.code
        _upload_report(manifest, work, report, deps)
    if err is not None:
        deps.notifier.send("falhou", code=err.code, retryable=err.retryable, detail=err.detail[-300:])
        print(f"falhou: {err}", file=sys.stderr)
        return err.exit_code
    deps.notifier.send("concluiu", splatBytes=report.splat_bytes, gaussians=report.gaussians)
    return 0
