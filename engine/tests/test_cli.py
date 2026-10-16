import json
import subprocess
import sys


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "visitta_engine", *args], capture_output=True, text=True, env=env)


def test_help():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "run" in result.stdout


def test_invalid_manifest_file_exits_30(tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"v": 2}))
    result = run_cli("run", "--manifest-file", str(bad), "--workdir", str(tmp_path / "w"))
    assert result.returncode == 30
    assert "MANIFEST_INVALID" in result.stderr


def test_unreachable_manifest_url_exits_20(tmp_path):
    result = run_cli("run", "--manifest-url", "http://127.0.0.1:9/m.json", "--workdir", str(tmp_path / "w"))
    assert result.returncode == 20
    assert "HOST_DOWNLOAD" in result.stderr


def test_missing_manifest_source_exits_30(tmp_path):
    env = {"PATH": "/usr/bin:/bin"}
    result = run_cli("run", "--workdir", str(tmp_path / "w"), env=env)
    assert result.returncode == 30
