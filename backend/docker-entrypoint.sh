#!/bin/sh
# Keep the venv volume in sync with the image. Named volumes are not refreshed by `--build`,
# so recreate the venv if the image's Python changed, and reinstall deps if requirements changed.
set -e
STAMP="$VIRTUAL_ENV/.requirements.sha256"

# pyvenv.cfg records the Python the venv was built with (bin/python is just a symlink).
WANT="$(/usr/local/bin/python -c 'import platform; print(platform.python_version())')"
HAVE="$(sed -n 's/^version *= *//p' "$VIRTUAL_ENV/pyvenv.cfg" 2>/dev/null || true)"
if [ "$WANT" != "$HAVE" ]; then
    echo "[entrypoint] Python version changed, recreating venv..."
    /usr/local/bin/python -m venv --clear "$VIRTUAL_ENV"
    rm -f "$STAMP"
fi

CURRENT="$(cat requirements.txt requirements-dev.txt | sha256sum)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$CURRENT" ]; then
    echo "[entrypoint] requirements changed, updating venv..."
    pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
    echo "$CURRENT" > "$STAMP"
fi
exec "$@"
