from pathlib import Path

from make_manifest import build_manifest
from visitta_engine.manifest import parse_manifest


def test_build_manifest_is_valid_and_lists_uploads(tmp_path):
    files = [tmp_path / "sala.MOV", tmp_path / "IMG_1.HEIC", tmp_path / "notas.txt"]
    for f in files:
        f.write_bytes(b"x")
    manifest, uploads = build_manifest(
        "apto-01", "boa", files,
        presign_get=lambda key: f"https://r2.example/{key}?get",
        presign_put=lambda key: f"https://r2.example/{key}?put",
    )
    m = parse_manifest(manifest)
    assert [i.kind for i in m.inputs] == ["video", "photo"]
    assert manifest["inputs"][0]["url"] == "https://r2.example/spike/apto-01/in/000.mov?get"
    assert manifest["outputs"]["splatUrl"] == "https://r2.example/spike/apto-01/out/tour.sog?put"
    assert manifest["outputs"]["viewerUrl"] == "https://r2.example/spike/apto-01/out/viewer.html?put"
    assert manifest["callback"] is None
    assert uploads == {
        "spike/apto-01/in/000.mov": str(files[0]),
        "spike/apto-01/in/001.heic": str(files[1]),
    }
