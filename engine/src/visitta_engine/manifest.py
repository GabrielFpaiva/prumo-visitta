"""Contrato v1 entre quem dispara o job e a instância de GPU."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlparse

from .errors import EngineError

PRESET_NAMES = ("rapida", "boa", "alta")
MAX_INPUTS = 320
VIDEO_EXTS = frozenset({".mp4", ".mov", ".m4v"})
PHOTO_EXTS = frozenset({".jpg", ".jpeg", ".png", ".heic", ".heif"})
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost"})


@dataclass(frozen=True)
class InputFile:
    url: str
    kind: Literal["video", "photo"]
    name: str
    ext: str


@dataclass(frozen=True)
class Outputs:
    splat_url: str
    report_url: str
    viewer_url: str | None


@dataclass(frozen=True)
class Callback:
    url: str
    secret: str


@dataclass(frozen=True)
class Manifest:
    job_id: str
    preset: str
    inputs: tuple[InputFile, ...]
    outputs: Outputs
    callback: Callback | None


def _fail(detail: str) -> EngineError:
    return EngineError("MANIFEST_INVALID", detail)


def _url(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(f"{field} ausente")
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value
    if parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS:
        return value
    raise _fail(f"{field} precisa ser https")


def _input(raw: Any, index: int) -> InputFile:
    if not isinstance(raw, dict):
        raise _fail(f"inputs[{index}] inválido")
    kind = raw.get("kind")
    name = raw.get("name")
    if kind not in ("video", "photo"):
        raise _fail(f"inputs[{index}].kind inválido")
    if not isinstance(name, str) or not name:
        raise _fail(f"inputs[{index}].name ausente")
    ext = PurePosixPath(name).suffix.lower()
    allowed = VIDEO_EXTS if kind == "video" else PHOTO_EXTS
    if ext not in allowed:
        raise _fail(f"inputs[{index}] extensão {ext or '(nenhuma)'} não aceita para {kind}")
    return InputFile(url=_url(raw.get("url"), f"inputs[{index}].url"), kind=kind, name=name, ext=ext)


def parse_manifest(data: object) -> Manifest:
    if not isinstance(data, dict):
        raise _fail("manifesto não é um objeto")
    if data.get("v") != 1:
        raise _fail("versão do manifesto não suportada")
    job_id = data.get("jobId")
    if not isinstance(job_id, str) or not job_id:
        raise _fail("jobId ausente")
    preset = data.get("preset")
    if preset not in PRESET_NAMES:
        raise _fail(f"preset inválido: {preset}")
    raw_inputs = data.get("inputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise _fail("inputs vazio")
    if len(raw_inputs) > MAX_INPUTS:
        raise _fail(f"mais de {MAX_INPUTS} entradas")
    inputs = tuple(_input(raw, i) for i, raw in enumerate(raw_inputs))

    raw_out = data.get("outputs")
    if not isinstance(raw_out, dict):
        raise _fail("outputs ausente")
    viewer = raw_out.get("viewerUrl")
    outputs = Outputs(
        splat_url=_url(raw_out.get("splatUrl"), "outputs.splatUrl"),
        report_url=_url(raw_out.get("reportUrl"), "outputs.reportUrl"),
        viewer_url=_url(viewer, "outputs.viewerUrl") if viewer is not None else None,
    )

    raw_cb = data.get("callback")
    callback = None
    if raw_cb is not None:
        if not isinstance(raw_cb, dict) or not isinstance(raw_cb.get("secret"), str) or not raw_cb["secret"]:
            raise _fail("callback precisa de url e secret")
        callback = Callback(url=_url(raw_cb.get("url"), "callback.url"), secret=raw_cb["secret"])

    return Manifest(job_id=job_id, preset=preset, inputs=inputs, outputs=outputs, callback=callback)
