import json
import sys

import pytest

from visitta_engine.report import Report
from visitta_engine.runner import CommandFailed, SubprocessRunner


def test_runner_ok_writes_log(tmp_path):
    log = tmp_path / "x.log"
    SubprocessRunner().run([sys.executable, "-c", "print('ola')"], log=log)
    assert "ola" in log.read_text()


def test_runner_failure_keeps_stderr_tail(tmp_path):
    code = "import sys; sys.stderr.write('x' * 5000 + 'CUDA error: boom'); sys.exit(3)"
    with pytest.raises(CommandFailed) as exc:
        SubprocessRunner().run([sys.executable, "-c", code])
    assert exc.value.returncode == 3
    assert exc.value.stderr_tail.endswith("CUDA error: boom")
    assert len(exc.value.stderr_tail) <= 4000


def test_runner_missing_binary_is_command_failed():
    with pytest.raises(CommandFailed) as exc:
        SubprocessRunner().run(["definitely-not-a-binary-xyz"])
    assert exc.value.returncode == 127


def test_report_stage_times_and_json():
    entered = []
    report = Report(job_id="j1", preset="boa")
    with report.stage("colmap", on_enter=entered.append):
        pass
    assert entered == ["colmap"]
    assert report.stages["colmap"] >= 0
    data = json.loads(report.to_json())
    assert data["jobId"] == "j1"
    assert data["stages"]["colmap"] >= 0
    assert data["error"] is None


def test_report_stage_records_time_even_on_error():
    report = Report(job_id="j1", preset="boa")
    with pytest.raises(RuntimeError):
        with report.stage("treino"):
            raise RuntimeError("x")
    assert "treino" in report.stages
