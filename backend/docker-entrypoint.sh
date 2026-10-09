#!/bin/sh
# Re-install Python deps into the venv volume if the requirements files changed
# since the volume was created (named volumes are not refreshed by `--build`).
set -e
STAMP="$VIRTUAL_ENV/.requirements.sha256"
CURRENT="$(cat requirements.txt requirements-dev.txt | sha256sum)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$CURRENT" ]; then
    echo "[entrypoint] requirements changed, updating venv..."
    pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
    echo "$CURRENT" > "$STAMP"
fi
exec "$@"
