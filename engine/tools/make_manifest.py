"""Uso local no spike: sobe uma captura ao R2 e gera o manifesto com URLs assinadas (3h)."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path

from visitta_engine.manifest import PHOTO_EXTS, VIDEO_EXTS

EXPIRES_SECONDS = 3 * 60 * 60


def _kind(ext: str) -> str | None:
    return "video" if ext in VIDEO_EXTS else "photo" if ext in PHOTO_EXTS else None


def build_manifest(
    job_id: str,
    preset: str,
    files: list[Path],
    presign_get: Callable[[str], str],
    presign_put: Callable[[str], str],
    *,
    prefix: str = "spike",
) -> tuple[dict, dict[str, str]]:
    base = f"{prefix}/{job_id}"
    inputs, uploads = [], {}
    for kind, path in sorted(
        ((k, p) for p in files if (k := _kind(p.suffix.lower()))), key=lambda kp: (kp[0] != "video", kp[1].name.lower())
    ):
        ext = path.suffix.lower()
        key = f"{base}/in/{len(inputs):03d}{ext}"
        uploads[key] = str(path)
        inputs.append({"url": presign_get(key), "kind": kind, "name": path.name})
    manifest = {
        "v": 1,
        "jobId": job_id,
        "preset": preset,
        "inputs": inputs,
        "outputs": {
            "splatUrl": presign_put(f"{base}/out/tour.sog"),
            "reportUrl": presign_put(f"{base}/out/report.json"),
            "viewerUrl": presign_put(f"{base}/out/viewer.html"),
        },
        "callback": None,
    }
    return manifest, uploads


def main() -> None:
    import boto3

    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--preset", default="boa", choices=["rapida", "boa", "alta"])
    parser.add_argument("--bucket", default="visitta-spike")
    args = parser.parse_args()

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

    def presign(method: str) -> Callable[[str], str]:
        return lambda key: s3.generate_presigned_url(
            method, Params={"Bucket": args.bucket, "Key": key}, ExpiresIn=EXPIRES_SECONDS
        )

    job_id = f"{args.job}-{args.preset}"
    files = [p for p in args.dir.iterdir() if p.is_file()]
    manifest, uploads = build_manifest(job_id, args.preset, files, presign("get_object"), presign("put_object"))
    for key, local in uploads.items():
        print(f"subindo {local} → {key}")
        s3.upload_file(local, args.bucket, key)
    manifest_key = f"spike/{job_id}/manifest.json"
    s3.put_object(Bucket=args.bucket, Key=manifest_key, Body=json.dumps(manifest).encode())

    print("\nVISITTA_MANIFEST_URL=" + presign("get_object")(manifest_key))
    print("\nSaídas (válidas por 3h depois do job; gere de novo se expirar):")
    for name in ("tour.sog", "viewer.html", "report.json"):
        print(f"  {name}: {presign('get_object')(f'spike/{job_id}/out/{name}')}")


if __name__ == "__main__":
    main()
