import json
from pathlib import Path

from helpers import make_photo
from visitta_engine.manifest import parse_manifest
from visitta_engine.pipeline import Deps, run_job
from visitta_engine.runner import CommandFailed
from visitta_engine.sfm import ModelSummary
from visitta_engine.transport import Notifier


class FakeRunner:
    """ffmpeg gera quadros; o trainer gera PLY; splat-transform gera o arquivo de saída."""

    def __init__(self, frames_per_video=60, train_error=None, broken_videos=(),
                 video_error=(1, "Invalid data found when processing input")):
        self.frames_per_video = frames_per_video
        self.train_error = train_error
        self.broken_videos = set(broken_videos)
        self.video_error = video_error
        self.cmds = []

    def run(self, cmd, *, cwd=None, log=None):
        self.cmds.append(list(cmd))
        if cmd[0] == "ffmpeg":
            video = Path(cmd[cmd.index("-i") + 1])
            if video.name in self.broken_videos:
                raise CommandFailed(cmd, *self.video_error)
            pattern = Path(cmd[-1])
            for i in range(self.frames_per_video):
                make_photo(pattern.parent / f"f_{i + 1:05d}.jpg", size=(64, 48), seed=i)
        elif cmd[0] == "splat-transform":
            Path(cmd[-1]).write_bytes(b"SOG" * 100)
        else:  # trainer
            if self.train_error:
                raise CommandFailed(cmd, 1, self.train_error)
            result = Path(cmd[cmd.index("--result_dir") + 1])
            ply = result / "ply" / "point_cloud_29999.ply"
            ply.parent.mkdir(parents=True)
            ply.write_bytes(b"ply\nelement vertex 500000\nend_header\n")
            (result / "stats").mkdir()
            (result / "stats" / "val_step29999.json").write_text(json.dumps({"psnr": 25.0}))


class FakeColmap:
    def __init__(self, ratio=0.9, error=None):
        self.ratio = ratio
        self.error = error

    def extract(self, database, images):
        if self.error:
            raise self.error
        self.total = len(list(images.rglob("*.jpg")))

    def match(self, database, *, sequential):
        pass

    def map(self, database, images, output):
        (output / "0").mkdir(parents=True)
        (output / "0" / "images.bin").write_bytes(b"x")
        return [ModelSummary(0, int(self.total * self.ratio))]


def setup(store, tmp_path, *, photos=0, videos=0, callback=True):
    inputs = []
    for i in range(videos):
        store.objects[f"/in/v{i}"] = b"video"
        inputs.append({"url": store.url(f"/in/v{i}"), "kind": "video", "name": f"comodo{i}.mp4"})
    for i in range(photos):
        p = make_photo(tmp_path / "src" / f"IMG_{i:04d}.jpg", size=(64, 48), seed=100 + i)
        store.objects[f"/in/p{i}"] = p.read_bytes()
        inputs.append({"url": store.url(f"/in/p{i}"), "kind": "photo", "name": p.name})
    data = {
        "v": 1, "jobId": "apto-01", "preset": "boa", "inputs": inputs,
        "outputs": {"splatUrl": store.url("/out/tour.sog"), "reportUrl": store.url("/out/report.json"),
                    "viewerUrl": store.url("/out/viewer.html")},
        "callback": {"url": store.url("/callback"), "secret": "k"} if callback else None,
    }
    return parse_manifest(data)


def deps_for(manifest, runner, colmap=None):
    return Deps(runner=runner, colmap=colmap or FakeColmap(), notifier=Notifier(manifest.callback, manifest.job_id),
                trainer_python="py", trainer_script="trainer.py", gpu="RTX 4090", transfer_backoff=0)


def event_types(store):
    return [e["type"] for e, _ in store.events]


def report_of(store):
    return json.loads(store.objects["/out/report.json"])


def test_success_uploads_outputs_and_report(store, tmp_path):
    m = setup(store, tmp_path, photos=10, videos=1)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner()))
    assert code == 0
    assert store.objects["/out/tour.sog"].startswith(b"SOG")
    assert "/out/viewer.html" in store.objects
    report = report_of(store)
    assert report["photos"] == 10 and report["videos"] == 1
    assert report["imagesTotal"] == 40  # 10 fotos + 30 quadros (60 amostrados ÷ janela 2)
    assert report["gaussians"] == 500000 and report["psnr"] == 25.0 and report["gpu"] == "RTX 4090"
    assert report["error"] is None
    assert set(report["stages"]) == {"baixando", "quadros", "colmap", "treino", "compressao", "enviando"}
    assert event_types(store)[0] == "iniciou" and event_types(store)[-1] == "concluiu"


def test_gsplat_layout(store, tmp_path):
    m = setup(store, tmp_path, photos=0, videos=2)
    run_job(m, tmp_path / "work", deps_for(m, FakeRunner()))
    data = tmp_path / "work" / "data"
    assert (data / "sparse" / "0" / "images.bin").exists()
    assert sorted(p.name for p in (data / "images").iterdir()) == ["video0", "video1"]


def test_too_few_images(store, tmp_path):
    m = setup(store, tmp_path, photos=12)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner()))
    assert code == 10
    assert report_of(store)["error"] == "CAPTURE_TOO_FEW"
    last, _ = store.events[-1]
    assert last["type"] == "falhou" and last["code"] == "CAPTURE_TOO_FEW" and last["retryable"] is False


def test_insufficient_registration(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner(), FakeColmap(ratio=0.3)))
    assert code == 10
    assert report_of(store)["error"] == "CAPTURE_INSUFFICIENT"


def test_broken_video_is_skipped(store, tmp_path):
    m = setup(store, tmp_path, photos=0, videos=3)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner(broken_videos={"001.mp4"})))
    assert code == 0
    report = report_of(store)
    assert report["skippedVideos"] == 1 and report["imagesTotal"] == 60


def test_cuda_failure_is_retryable_host_error(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner(train_error="RuntimeError: CUDA error: device-side assert")))
    assert code == 20
    last, _ = store.events[-1]
    assert last["code"] == "HOST_CUDA" and last["retryable"] is True


def test_frames_cap_shared_between_videos(store, tmp_path):
    m = setup(store, tmp_path, photos=0, videos=2)
    run_job(m, tmp_path / "work", deps_for(m, FakeRunner(frames_per_video=1000)))
    assert report_of(store)["imagesTotal"] == 300


def test_works_without_callback(store, tmp_path):
    m = setup(store, tmp_path, videos=1, photos=10, callback=False)
    assert run_job(m, tmp_path / "work", deps_for(m, FakeRunner())) == 0
    assert store.events == []


def test_full_disk_while_extracting_frames_is_host_disk(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    runner = FakeRunner(broken_videos={"000.mp4", "001.mp4"}, video_error=(1, "No space left on device"))
    assert run_job(m, tmp_path / "work", deps_for(m, runner)) == 20
    assert report_of(store)["error"] == "HOST_DISK"


def test_missing_ffmpeg_is_engine_error_not_bad_capture(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    runner = FakeRunner(broken_videos={"000.mp4", "001.mp4"}, video_error=(127, "No such file: ffmpeg"))
    assert run_job(m, tmp_path / "work", deps_for(m, runner)) == 30
    assert report_of(store)["error"] == "ENGINE_ERROR"


def test_ffmpeg_killed_by_signal_is_not_bad_capture(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    runner = FakeRunner(broken_videos={"000.mp4", "001.mp4"}, video_error=(-9, ""))
    assert run_job(m, tmp_path / "work", deps_for(m, runner)) == 30


def test_in_process_cuda_failure_is_retryable(store, tmp_path):
    m = setup(store, tmp_path, videos=2)
    colmap = FakeColmap(error=RuntimeError("CUDA error: no CUDA-capable device is detected"))
    assert run_job(m, tmp_path / "work", deps_for(m, FakeRunner(), colmap)) == 20


def test_failure_is_reported_even_when_report_cannot_be_written(store, tmp_path, monkeypatch):
    import errno

    from visitta_engine.report import Report

    def full(self):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Report, "to_json", full)
    m = setup(store, tmp_path, videos=2)
    code = run_job(m, tmp_path / "work", deps_for(m, FakeRunner(train_error="No space left on device")))
    assert code == 20
    last, _ = store.events[-1]
    assert last["type"] == "falhou" and last["code"] == "HOST_DISK"
