"""Write the API's OpenAPI document to frontend/src/lib/api/openapi.json.

`npm run api:types` runs this, then generates the frontend's TypeScript types from the file.
It imports the app without starting it, so no server or database is needed.
"""

import json
import os
import sys
from pathlib import Path

# Export the full API whatever the local .env says.
os.environ["STUB_API"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api" / "openapi.json"

if __name__ == "__main__":
    OUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
