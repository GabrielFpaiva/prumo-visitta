import json

import pytest

from visitta_engine.errors import EngineError
from visitta_engine.train import (
    PRESETS, compress, count_gaussians, find_final_ply, read_psnr, train_command,
)


def write_ply(path, n):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"ply\nformat binary_little_endian 1.0\nelement vertex {n}\nproperty float x\nend_header\n".encode() + b"\0" * 8)
    return path


def test_presets():
    assert PRESETS["boa"].max_steps == 30_000
    assert PRESETS["rapida"].max_steps == 7_000
    assert PRESETS["alta"].strategy == "mcmc"


def test_train_command(tmp_path):
    cmd = train_command(PRESETS["boa"], tmp_path / "data", tmp_path / "res", python="/opt/train/bin/python", trainer="/opt/gsplat/examples/simple_trainer.py")
    assert cmd[:3] == ["/opt/train/bin/python", "/opt/gsplat/examples/simple_trainer.py", "default"]
    joined = " ".join(cmd)
    assert f"--data-dir {tmp_path / 'data'}" in joined
    assert "--data-factor 1" in joined
    assert "--max-steps 30000" in joined
    assert "--ply-steps 30000" in joined
    assert "--save-ply" in cmd
    assert "--disable-viewer" in cmd


def test_find_final_ply_picks_highest_step(tmp_path):
    write_ply(tmp_path / "ply" / "point_cloud_6999.ply", 10)
    final = write_ply(tmp_path / "ply" / "point_cloud_29999.ply", 20)
    assert find_final_ply(tmp_path) == final


def test_find_final_ply_missing(tmp_path):
    with pytest.raises(EngineError) as exc:
        find_final_ply(tmp_path)
    assert exc.value.code == "ENGINE_ERROR"


def test_count_gaussians(tmp_path):
    assert count_gaussians(write_ply(tmp_path / "a.ply", 1234567)) == 1234567


def test_read_psnr(tmp_path):
    stats = tmp_path / "stats"
    stats.mkdir()
    (stats / "val_step6999.json").write_text(json.dumps({"psnr": 20.1}))
    (stats / "val_step29999.json").write_text(json.dumps({"psnr": 24.5}))
    assert read_psnr(tmp_path) == 24.5
    assert read_psnr(tmp_path / "nada") is None


class RecordingRunner:
    def __init__(self):
        self.cmds = []

    def run(self, cmd, *, cwd=None, log=None):
        self.cmds.append(list(cmd))


def test_compress_commands(tmp_path):
    runner = RecordingRunner()
    compress(tmp_path / "f.ply", tmp_path / "tour.sog", runner, viewer_html=tmp_path / "viewer.html")
    assert runner.cmds[0] == ["splat-transform", str(tmp_path / "f.ply"), "--filter-nan", str(tmp_path / "tour.sog")]
    assert runner.cmds[1] == ["splat-transform", str(tmp_path / "tour.sog"), str(tmp_path / "viewer.html")]


def test_compress_without_viewer(tmp_path):
    runner = RecordingRunner()
    compress(tmp_path / "f.ply", tmp_path / "tour.sog", runner)
    assert len(runner.cmds) == 1
