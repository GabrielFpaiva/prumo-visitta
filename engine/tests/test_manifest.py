import copy

import pytest

from visitta_engine.errors import EngineError
from visitta_engine.manifest import parse_manifest

VALID = {
    "v": 1,
    "jobId": "apto-01",
    "preset": "boa",
    "inputs": [
        {"url": "https://r2.example/in/0", "kind": "video", "name": "Sala de Estar.MOV"},
        {"url": "https://r2.example/in/1", "kind": "photo", "name": "IMG_0001.HEIC"},
    ],
    "outputs": {"splatUrl": "https://r2.example/out/tour.sog", "reportUrl": "https://r2.example/out/report.json"},
    "callback": None,
}


def with_change(path, value):
    data = copy.deepcopy(VALID)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


def test_parses_valid_manifest():
    m = parse_manifest(VALID)
    assert m.job_id == "apto-01"
    assert m.preset == "boa"
    assert [i.kind for i in m.inputs] == ["video", "photo"]
    assert [i.ext for i in m.inputs] == [".mov", ".heic"]
    assert m.outputs.viewer_url is None
    assert m.callback is None


def test_parses_callback_and_viewer():
    data = with_change(["callback"], {"url": "https://api.example/gpu", "secret": "s3cr3t"})
    data["outputs"]["viewerUrl"] = "https://r2.example/out/viewer.html"
    m = parse_manifest(data)
    assert m.callback is not None and m.callback.secret == "s3cr3t"
    assert m.outputs.viewer_url == "https://r2.example/out/viewer.html"


def test_localhost_http_is_allowed_for_tests():
    data = with_change(["inputs", 0, "url"], "http://127.0.0.1:8123/in/0")
    assert parse_manifest(data).inputs[0].url.startswith("http://127.0.0.1")


@pytest.mark.parametrize(
    "data",
    [
        "not a dict",
        with_change(["v"], 2),
        with_change(["jobId"], ""),
        with_change(["preset"], "ultra"),
        with_change(["inputs"], []),
        with_change(["inputs", 0, "kind"], "audio"),
        with_change(["inputs", 0, "name"], "planta.pdf"),
        with_change(["inputs", 1, "name"], "foto.mov"),
        with_change(["inputs", 0, "url"], "http://evil.example/in/0"),
        with_change(["outputs", "splatUrl"], ""),
        with_change(["callback"], {"url": "https://api.example/gpu"}),
    ],
)
def test_rejects_invalid_manifest(data):
    with pytest.raises(EngineError) as exc:
        parse_manifest(data)
    assert exc.value.code == "MANIFEST_INVALID"


def test_rejects_too_many_inputs():
    data = copy.deepcopy(VALID)
    data["inputs"] = [
        {"url": f"https://r2.example/in/{i}", "kind": "photo", "name": f"{i}.jpg"} for i in range(321)
    ]
    with pytest.raises(EngineError):
        parse_manifest(data)
