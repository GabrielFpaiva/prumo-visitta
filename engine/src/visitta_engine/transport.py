"""Entrada e saída do host: só URLs assinadas do job e callback assinado com HMAC."""

from __future__ import annotations

import errno
import hashlib
import hmac
import http.client
import json
import shutil
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .errors import EngineError
from .manifest import Callback

SIGNATURE_HEADER = "X-Visitta-Signature"
TIMEOUT_SECONDS = 60
# URLError, timeout, conexão e SSL são OSError; IncompleteRead e BadStatusLine são HTTPException.
_NETWORK_ERRORS = (OSError, http.client.HTTPException)


def _network_failure(exc: BaseException) -> str:
    """Disco cheio não é falha de rede: sobe como OSError para virar HOST_DISK."""
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        raise exc
    return str(exc)


def download(url: str, dest: Path, *, attempts: int = 3, backoff: float = 2.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = ""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp, dest.open("wb") as fh:
                shutil.copyfileobj(resp, fh, length=1 << 20)
                expected = resp.headers.get("Content-Length")
            # http.client não reclama de corpo menor que o Content-Length quando a conexão fecha
            if expected is not None and dest.stat().st_size != int(expected):
                raise http.client.IncompleteRead(b"", int(expected) - dest.stat().st_size)
            return
        except _NETWORK_ERRORS as exc:
            last = _network_failure(exc) or type(exc).__name__
            time.sleep(backoff * (attempt + 1))
    raise EngineError("HOST_DOWNLOAD", last)


def upload(path: Path, url: str, content_type: str, *, attempts: int = 3, backoff: float = 2.0) -> None:
    size = path.stat().st_size
    last = ""
    for attempt in range(attempts):
        try:
            with path.open("rb") as fh:
                req = urllib.request.Request(
                    url, data=fh, method="PUT",
                    headers={"Content-Type": content_type, "Content-Length": str(size)},
                )
                with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS):
                    return
        except _NETWORK_ERRORS as exc:
            last = _network_failure(exc) or type(exc).__name__
            time.sleep(backoff * (attempt + 1))
    raise EngineError("HOST_UPLOAD", last)


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class Notifier:
    """Avisa o orquestrador. Falha de callback nunca derruba o job: o prazo do orquestrador cobre."""

    def __init__(self, callback: Callback | None, job_id: str) -> None:
        self.callback = callback
        self.job_id = job_id
        self.stage: str | None = None

    def send(self, type: str, **fields: object) -> None:
        if self.callback is None:
            return
        payload = {"v": 1, "jobId": self.job_id, "type": type, "stage": self.stage,
                   "at": datetime.now(UTC).isoformat(), **fields}
        body = json.dumps(payload, ensure_ascii=False).encode()
        req = urllib.request.Request(
            self.callback.url, data=body, method="POST",
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: sign(body, self.callback.secret)},
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as exc:  # noqa: BLE001 — callback nunca derruba o job
            print(f"callback {type} falhou: {exc!r}", file=sys.stderr)

    @contextmanager
    def heartbeat(self, interval: float = 120.0) -> Iterator[None]:
        stop = threading.Event()

        def beat() -> None:
            while not stop.wait(interval):
                self.send("progresso")

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=5)
