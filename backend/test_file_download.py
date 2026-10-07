"""Generated-file download route checks."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)
    generated_dir = Path(__file__).parent / "generated"
    generated_dir.mkdir(exist_ok=True)
    probe = generated_dir / "download_probe.pptx"
    probe.write_bytes(b"pptx-probe-bytes")
    try:
        served = client.get(f"/api/files/{probe.name}")
        assert served.status_code == 200, served.text
        assert served.content == b"pptx-probe-bytes", "Downloaded bytes differ from the generated file."
        assert f'filename="{probe.name}"' in served.headers.get("content-disposition", "")

        assert client.get("/api/files/not_there.pptx").status_code == 404

        # Traversal and separator names must never leave generated/, even with a .pptx suffix.
        assert client.get("/api/files/..%2Fsecret.pptx").status_code == 404
        assert client.get("/api/files/sub/secret.pptx").status_code == 404

        # Only decks are downloadable: internal metrics and presentation JSON stay private.
        assert client.get("/api/files/metrics.jsonl").status_code == 404
        assert client.get("/api/files/presentation_demo_v1.json").status_code == 404
    finally:
        probe.unlink(missing_ok=True)
    print("Download route passed: decks are served; missing, traversal, and non-deck names return 404.")


if __name__ == "__main__":
    main()
