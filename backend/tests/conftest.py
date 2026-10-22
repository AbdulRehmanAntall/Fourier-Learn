import importlib.util
import os
import tempfile
from pathlib import Path

# Tests must not need Postgres or touch the real media folder.
# Set these before the app (and its cached settings) is imported.
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1:1/test"
os.environ["MEDIA_DIR"] = str(Path(tempfile.gettempdir()) / "fourierlearn-test-media")
# No artificial delay on stub responses in tests.
os.environ["STUB_LATENCY_MS"] = "0"

# `npm run setup` installs everything except Manim on machines without Cairo/Pango. The app
# still runs there, so skip the tests that need Manim instead of failing them.
if importlib.util.find_spec("manim") is None:
    collect_ignore = ["test_layout.py", "test_primitives.py", "test_render_engine.py"]
