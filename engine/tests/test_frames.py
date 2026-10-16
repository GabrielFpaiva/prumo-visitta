import shutil
import subprocess

import cv2
import numpy as np
import pytest
from PIL import Image

from visitta_engine.frames import extract_video_frames, laplacian_variance, select_sharpest
from visitta_engine.runner import CommandFailed, SubprocessRunner

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")


def test_select_sharpest_picks_best_per_window():
    assert select_sharpest([1, 5, 3, 2, 9, 0, 4], window=2, cap=10) == [1, 2, 4, 6]


def test_select_sharpest_caps_uniformly():
    picks = select_sharpest(list(range(100)), window=1, cap=10)
    assert picks == [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_select_sharpest_zero_cap():
    assert select_sharpest([1, 2, 3], window=1, cap=0) == []


def test_laplacian_prefers_sharp_image(tmp_path):
    rng = np.random.default_rng(0)
    sharp = rng.integers(0, 255, (200, 200), dtype=np.uint8)
    blurred = cv2.GaussianBlur(sharp, (21, 21), 8)
    cv2.imwrite(str(tmp_path / "s.png"), sharp)
    cv2.imwrite(str(tmp_path / "b.png"), blurred)
    assert laplacian_variance(tmp_path / "s.png") > laplacian_variance(tmp_path / "b.png")
    assert laplacian_variance(tmp_path / "nao-existe.png") == 0.0


def make_video(path, size, seconds=3):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"testsrc=duration={seconds}:size={size}:rate=30", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path


@needs_ffmpeg
def test_extracts_landscape_video(tmp_path):
    video = make_video(tmp_path / "sala.mp4", "1920x1080")
    frames = extract_video_frames(video, tmp_path / "out", SubprocessRunner(), cap=300)
    assert len(frames) == 6  # 3 s × 4 fps ÷ janela 2
    assert frames[0].name == "q_0000.jpg"
    with Image.open(frames[0]) as im:
        assert im.size == (1600, 900)
    assert not list(tmp_path.glob("_raw_*")), "pasta temporária deve ser apagada"


@needs_ffmpeg
def test_extracts_portrait_video(tmp_path):
    video = make_video(tmp_path / "em-pe.mp4", "1080x1920")
    frames = extract_video_frames(video, tmp_path / "out", SubprocessRunner(), cap=300)
    with Image.open(frames[0]) as im:
        assert im.size == (900, 1600)


@needs_ffmpeg
def test_respects_cap(tmp_path):
    video = make_video(tmp_path / "longo.mp4", "640x360", seconds=5)
    frames = extract_video_frames(video, tmp_path / "out", SubprocessRunner(), cap=4)
    assert len(frames) == 4


@needs_ffmpeg
def test_unreadable_video_raises_command_failed(tmp_path):
    bad = tmp_path / "quebrado.mp4"
    bad.write_bytes(b"lixo")
    with pytest.raises(CommandFailed):
        extract_video_frames(bad, tmp_path / "out", SubprocessRunner(), cap=300)
