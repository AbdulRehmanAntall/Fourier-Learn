import os
import tempfile
from pathlib import Path

# Tests must not need Postgres or touch the real media folder.
# Set these before the app (and its cached settings) is imported.
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1:1/test"
os.environ["MEDIA_DIR"] = str(Path(tempfile.gettempdir()) / "fourierlearn-test-media")
