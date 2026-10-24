"""`python -m app.workers`: start a render worker (see app/workers/render_worker.py)."""

import sys

from app.workers.render_worker import main

sys.exit(main())
