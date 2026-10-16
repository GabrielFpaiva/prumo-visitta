import hashlib
import hmac
import json
import time

import pytest

from visitta_engine.errors import EngineError
from visitta_engine.manifest import Callback
from visitta_engine.transport import Notifier, download, sign, upload


def test_download_ok(store, tmp_path):
    store.objects["/in/0"] = b"abc"
    download(store.url("/in/0"), tmp_path / "x.bin", backoff=0)
    assert (tmp_path / "x.bin").read_bytes() == b"abc"


def test_download_retries_then_succeeds(store, tmp_path):
    store.objects["/in/0"] = b"abc"
    store.fail["/in/0"] = 2
    download(store.url("/in/0"), tmp_path / "x.bin", backoff=0)
    assert (tmp_path / "x.bin").read_bytes() == b"abc"


def test_download_gives_up(store, tmp_path):
    with pytest.raises(EngineError) as exc:
        download(store.url("/nao-existe"), tmp_path / "x.bin", backoff=0)
    assert exc.value.code == "HOST_DOWNLOAD"


def test_upload_ok_and_failure(store, tmp_path):
    f = tmp_path / "tour.sog"
    f.write_bytes(b"splat")
    upload(f, store.url("/out/tour.sog"), "application/octet-stream", backoff=0)
    assert store.objects["/out/tour.sog"] == b"splat"
    store.fail["/out/r.json"] = 5
    with pytest.raises(EngineError) as exc:
        upload(f, store.url("/out/r.json"), "application/json", backoff=0)
    assert exc.value.code == "HOST_UPLOAD"


def test_sign_is_hmac_sha256():
    expected = hmac.new(b"k", b"body", hashlib.sha256).hexdigest()
    assert sign(b"body", "k") == f"sha256={expected}"


def test_notifier_sends_signed_events(store):
    n = Notifier(Callback(url=store.url("/callback"), secret="k"), job_id="j1")
    n.send("concluiu", splatBytes=10)
    body, signature = store.events[0]
    assert body["type"] == "concluiu" and body["jobId"] == "j1" and body["splatBytes"] == 10
    raw = store.objects["/_raw_events"].splitlines()[0]
    assert signature == sign(raw, "k")


def test_notifier_without_callback_is_noop():
    Notifier(None, job_id="j1").send("iniciou")


def test_notifier_never_raises_when_callback_is_down():
    Notifier(Callback(url="http://127.0.0.1:9/callback", secret="k"), job_id="j1").send("iniciou")


def test_heartbeat_reports_current_stage(store):
    n = Notifier(Callback(url=store.url("/callback"), secret="k"), job_id="j1")
    n.stage = "treino"
    with n.heartbeat(interval=0.05):
        time.sleep(0.2)
    beats = [b for b, _ in store.events if b["type"] == "progresso"]
    assert len(beats) >= 2
    assert all(b["stage"] == "treino" for b in beats)


def test_truncated_download_is_retried(store, tmp_path):
    store.objects["/in/0"] = b"v" * 100_000
    store.truncate["/in/0"] = 1
    download(store.url("/in/0"), tmp_path / "x.bin", backoff=0)
    assert (tmp_path / "x.bin").stat().st_size == 100_000


def test_always_truncated_download_is_host_error(store, tmp_path):
    store.objects["/in/0"] = b"v" * 100_000
    store.truncate["/in/0"] = 99
    with pytest.raises(EngineError) as exc:
        download(store.url("/in/0"), tmp_path / "x.bin", backoff=0)
    assert exc.value.code == "HOST_DOWNLOAD"


def test_full_disk_during_download_is_not_a_network_error(store, tmp_path, monkeypatch):
    import errno
    import shutil

    store.objects["/in/0"] = b"abc"

    def full(*args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(shutil, "copyfileobj", full)
    with pytest.raises(OSError) as exc:
        download(store.url("/in/0"), tmp_path / "x.bin", backoff=0)
    assert exc.value.errno == errno.ENOSPC


@pytest.fixture
def garbage_server():
    """Responde lixo em vez de HTTP: urllib levanta BadStatusLine, que não é URLError."""
    import socket
    import threading

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            conn.recv(65536)
            conn.sendall(b"isto nao e http\r\n\r\n")
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}/callback"
    srv.close()


def test_notifier_never_raises_on_malformed_response(garbage_server):
    Notifier(Callback(url=garbage_server, secret="k"), job_id="j1").send("iniciou")
