import pytest

from visitta_engine.errors import EngineError, classify_command_failure


def test_capture_codes_are_not_retryable_and_exit_10():
    err = EngineError("CAPTURE_INSUFFICIENT", "20/100")
    assert err.category == "capture"
    assert err.retryable is False
    assert err.exit_code == 10
    assert "20/100" in str(err)


def test_host_codes_are_retryable_and_exit_20():
    err = EngineError("HOST_DOWNLOAD")
    assert err.category == "host"
    assert err.retryable is True
    assert err.exit_code == 20


def test_engine_and_manifest_codes_exit_30():
    assert EngineError("ENGINE_ERROR").exit_code == 30
    assert EngineError("MANIFEST_INVALID").exit_code == 30
    assert EngineError("MANIFEST_INVALID").retryable is False


def test_unknown_code_is_rejected():
    with pytest.raises(ValueError):
        EngineError("WHATEVER")


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        ("OSError: [Errno 28] No space left on device", "HOST_DISK"),
        ("RuntimeError: CUDA error: an illegal memory access", "HOST_CUDA"),
        ("torch.OutOfMemoryError: CUDA out of memory", "HOST_CUDA"),
        ("NVIDIA-SMI has failed because it couldn't communicate", "HOST_CUDA"),
        ("KeyError: 'image_042.jpg'", "ENGINE_ERROR"),
    ],
)
def test_classify_command_failure(stderr, code):
    assert classify_command_failure(stderr) == code
