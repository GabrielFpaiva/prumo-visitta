# visitta-engine

Pipeline: entradas (vídeo/fotos) → quadros → COLMAP (pycolmap) → gsplat → `splat-transform` (.sog).

    uv sync --extra colmap
    uv run pytest
    uv run python -m visitta_engine run --manifest-file manifest.json --workdir ./work

## Manifesto v1

    {
      "v": 1,
      "jobId": "apto-01",
      "preset": "boa",
      "inputs": [{"url": "https://...", "kind": "video", "name": "sala.mp4"}],
      "outputs": {"splatUrl": "https://...", "reportUrl": "https://...", "viewerUrl": "https://..."},
      "callback": {"url": "https://...", "secret": "..."}
    }

`viewerUrl` e `callback` são opcionais. Exit codes: 0 ok, 10 captura, 20 host, 30 motor/manifesto.
