"""Execução de comandos externos (ffmpeg, gsplat, splat-transform) atrás de um protocolo."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

TAIL_CHARS = 4000


class CommandFailed(Exception):
    def __init__(self, cmd: Sequence[str], returncode: int, stderr_tail: str) -> None:
        super().__init__(f"{cmd[0]} saiu com {returncode}")
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stderr_tail = stderr_tail


class Runner(Protocol):
    def run(self, cmd: Sequence[str], *, cwd: Path | None = None, log: Path | None = None) -> None: ...


class SubprocessRunner:
    def run(self, cmd: Sequence[str], *, cwd: Path | None = None, log: Path | None = None) -> None:
        try:
            proc = subprocess.run(
                list(cmd), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace"
            )
        except FileNotFoundError as exc:
            raise CommandFailed(cmd, 127, str(exc)) from exc
        if log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a") as fh:
                fh.write(f"$ {' '.join(cmd)}\n{proc.stdout}\n")
        if proc.returncode != 0:
            raise CommandFailed(cmd, proc.returncode, proc.stdout[-TAIL_CHARS:])
