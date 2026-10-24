"""Check the Phase 3 path end to end against a running stack (milestone M2).

Logs in with the stub's test student, submits a lesson (by default the example
examples/gradient_of_line.lesson.json) to POST /api/dev/render, and waits for a worker to make
its first module playable and then every module ready. Needs the API, Postgres (migrated and
seeded) and at least one worker:

    python scripts/check_dev_lesson.py [--lesson examples/x.lesson.json]
                                       [--api http://localhost:8000] [--timeout 600]

Prints the timings and exits with 1 if anything is missing or too slow.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "gradient_of_line.lesson.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, default=EXAMPLE)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=30, trust_env=False) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "student@fourierlearn.test", "password": "password123"},
        )
        login.raise_for_status()
        created = client.post("/api/dev/render", json=json.loads(args.lesson.read_text()))
        if created.status_code != 200:
            print(f"POST /api/dev/render failed: {created.status_code} {created.text}")
            return 1
        lesson_id = created.json()["lesson_id"]
        print(f"lesson {lesson_id} created; waiting for a worker")

        started = time.monotonic()
        playable = None
        while time.monotonic() - started < args.timeout:
            current = client.get(f"/api/lessons/{lesson_id}/current-module").json()
            if current["status"] == "failed":
                print(f"the first module failed: {current['failure']}")
                return 1
            if current["status"] == "ready" and playable is None:
                playable = time.monotonic() - started
                manifest = client.get(f"/api/variants/{current['cache_key']}/manifest").json()
                if manifest["beats"][0]["index"] != 0:
                    print("the manifest does not start at beat 0")
                    return 1
                print(f"first module playable after {playable:.1f} s ({manifest['voice']})")
            lesson = client.get(f"/api/lessons/{lesson_id}").json()
            statuses = [module["render_status"] for module in lesson["modules"]]
            if "failed" in statuses:
                print(f"a module failed: {statuses}")
                return 1
            if all(status == "ready" for status in statuses) and playable is not None:
                print(f"every module ready after {time.monotonic() - started:.1f} s")
                return 0
            time.sleep(1)
        print(f"timed out after {args.timeout:.0f} s: {statuses}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
