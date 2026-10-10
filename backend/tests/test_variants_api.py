import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

KEY = "a" * 64


def write_manifest(complete: bool):
    directory = get_settings().media_dir / "variants" / KEY
    (directory / "beats").mkdir(parents=True, exist_ok=True)
    (directory / "beats" / "0.mp4").write_bytes(b"not really a video")
    beat = {
        "index": 0,
        "primitive_id": "GradientTriangle",
        "video": "beats/0.mp4",
        "duration_s": 12.5,
        "steps": [{"start_s": 0, "end_s": 12.5, "narration": "The gradient is 2."}],
    }
    manifest = {
        "cache_key": KEY,
        "level": 2,
        "voice": "default",
        "library_version": "0.1.0",
        "beat_count": 1 if complete else 2,
        "beats": [beat],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))


def test_manifest_listing_and_media():
    write_manifest(complete=True)
    with TestClient(app) as client:
        manifest = client.get(f"/api/variants/{KEY}/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["beats"][0]["video"] == "beats/0.mp4"

        listing = client.get("/api/dev/variants").json()
        entry = next(item for item in listing if item["cache_key"] == KEY)
        assert entry == {
            "cache_key": KEY,
            "level": 2,
            "beat_count": 1,
            "beats_ready": 1,
            "complete": True,
            "duration_s": 12.5,
            "primitives": ["GradientTriangle"],
        }

        video = client.get(f"/media/variants/{KEY}/beats/0.mp4")
        assert video.status_code == 200
        assert video.content == b"not really a video"


def test_unknown_or_malformed_keys_are_not_found():
    with TestClient(app) as client:
        assert client.get(f"/api/variants/{'b' * 64}/manifest").status_code == 404
        assert client.get("/api/variants/..%2F..%2Fetc/manifest").status_code == 404
        assert client.get("/api/variants/ABC/manifest").status_code == 404
