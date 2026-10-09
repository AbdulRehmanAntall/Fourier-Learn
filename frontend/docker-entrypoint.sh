#!/bin/sh
# Re-install npm deps into the node_modules volume if package-lock.json changed
# since the volume was created (named volumes are not refreshed by `--build`).
set -e
STAMP=node_modules/.package-lock.sha256
if ! sha256sum -c "$STAMP" >/dev/null 2>&1; then
    echo "[entrypoint] package-lock.json changed, running npm install..."
    npm install --no-audit --no-fund
    sha256sum package-lock.json > "$STAMP"
fi
exec "$@"
