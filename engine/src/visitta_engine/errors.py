"""Códigos de erro do motor (spec §8) e como cada um sai do processo."""

CAPTURE_CODES = frozenset({"CAPTURE_TOO_FEW", "CAPTURE_INSUFFICIENT"})
HOST_CODES = frozenset({"HOST_DOWNLOAD", "HOST_UPLOAD", "HOST_CUDA", "HOST_DISK"})
ENGINE_CODES = frozenset({"ENGINE_ERROR", "MANIFEST_INVALID"})

_EXIT_CODES = {"capture": 10, "host": 20, "engine": 30}


class EngineError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in CAPTURE_CODES | HOST_CODES | ENGINE_CODES:
            raise ValueError(f"código de erro desconhecido: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail

    @property
    def category(self) -> str:
        if self.code in CAPTURE_CODES:
            return "capture"
        if self.code in HOST_CODES:
            return "host"
        return "engine"

    @property
    def retryable(self) -> bool:
        return self.code in HOST_CODES

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.category]


def classify_command_failure(stderr_tail: str) -> str:
    """Decide se a falha de um comando externo é do host (repetível) ou do motor."""
    text = stderr_tail.lower()
    if "no space left" in text:
        return "HOST_DISK"
    if "cuda" in text or "nvidia" in text:
        return "HOST_CUDA"
    return "ENGINE_ERROR"
