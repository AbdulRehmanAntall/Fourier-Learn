# FourierLearn

Turn plain-text maths prompts into narrated, animated O-Level maths lessons (Manim), with difficulty
adapted by a learner model (Bayesian Knowledge Tracing).

> **Status: Phases 1 and 3 of [the plan](docs/PLAN.md) are done in the backend; Phase 2 (the
> screens) is under way.**
>
> - **The render engine** turns a module request (validated primitives, parameters and narration)
>   into a narrated, cached module video at any of the three difficulty levels. The library has
>   the seven primitives of the report's Table 5.2 and is growing to cover the O Level syllabus
>   ([coverage](docs/primitive-coverage.md)): 17 primitives so far.
> - **The render queue and workers** render hand-written lessons in the background; the first beat
>   plays before the rest is done ([Lessons through the queue](#lessons-through-the-queue-phase-3)).
> - **Every API endpoint the frontend needs exists.** Lessons from the queue are served from the
>   database; the rest is a stub with sample data and real example videos
>   ([the stub API](#the-stub-api-phase-2)). The frontend team's guide is
>   [docs/frontend.md](docs/frontend.md).
> - **Not yet:** lesson planning with an LLM (Phase 4) and the learner model, BKT (Phase 5).

| Part     | Stack                                                                                                |
| -------- | ---------------------------------------------------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy 2 + Alembic, psycopg 3, SymPy, Manim CE |
| Frontend | Next.js 16 (App Router), TypeScript, ESLint, Tailwind CSS                                            |
| Database | PostgreSQL 16                                                                                        |
| Tooling  | Docker + Docker Compose, Node scripts (cross-platform), Git                                          |

There are two ways to run the project. Pick one:

- **Docker (recommended):** you only need Git and Docker Desktop. FFmpeg, LaTeX, Cairo, Pango and
  the espeak-ng voice are installed inside the backend image, so rendering works the same on
  every OS.
- **Native:** faster reloads and easier debugging, but you install Python, Node, FFmpeg, LaTeX and
  espeak-ng yourself.

---

## Prerequisites

Always needed: **Git**. For Docker you also need **Docker Desktop**. For native you also need
**Python 3.12** (exact version in `.python-version`), **Node 24 LTS** (exact version in `.nvmrc`),
and, if you want to render natively, **FFmpeg**, **LaTeX**, **Cairo/Pango** and **espeak-ng** (the
narration voice).

### Windows 10/11

1. **Git:** <https://git-scm.com/download/win>
2. **Docker Desktop:** install WSL2 first. In an _admin_ PowerShell run `wsl --install`, then reboot.
   Then install Docker Desktop (<https://docs.docker.com/desktop/setup/install/windows-install/>)
   and keep "Use WSL 2 based engine" ticked.
3. **Native only:**
   - Python 3.12: `winget install Python.Python.3.12`, or the **3.12.10** installer from
     <https://www.python.org/downloads/windows/> (tick **"Add python.exe to PATH"**). Any 3.12.x
     works; python.org has no Windows installers for later 3.12 releases.
     The `py` launcher (`py -3.12`) is used automatically, even if another version is your default.
   - Node 24 LTS: <https://nodejs.org/>, or `nvm-windows` and then `nvm install 24.21.0`.
   - FFmpeg: `winget install Gyan.FFmpeg`. Open a new terminal afterwards.
   - LaTeX: **MiKTeX** (<https://miktex.org/download>). In the MiKTeX Console, set "Install missing
     packages on-the-fly" to **Yes**. **TeX Live** (<https://tug.org/texlive/windows.html>) also
     works.
   - Cairo/Pango: nothing to do, because the Windows wheels for Manim's dependencies include them.
   - espeak-ng: `winget install eSpeak-NG.eSpeak-NG`, or the installer from
     <https://github.com/espeak-ng/espeak-ng/releases>. Add its folder (for example
     `C:\Program Files\eSpeak NG`) to PATH, then open a new terminal.

### macOS (Homebrew)

```bash
# Install Homebrew first if needed: https://brew.sh
brew install git python@3.12 node@24 ffmpeg cairo pango pkg-config espeak-ng
brew install --cask mactex-no-gui        # full LaTeX (~5 GB), or the smaller: brew install --cask basictex
brew install --cask docker               # Docker Desktop (or download from docker.com)
```

If you use BasicTeX, add the extra packages that Manim's install guide lists:
`sudo tlmgr update --self && sudo tlmgr install standalone preview doublestroke relsize fundus-calligra wasysym physics dvisvgm rsfs wasy cm-super everysel setspace`.
Open a new terminal after installing LaTeX so `latex` is on your PATH.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv ffmpeg \
  build-essential pkg-config libcairo2-dev libpango1.0-dev \
  texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-science cm-super dvisvgm \
  espeak-ng
```

- Python 3.12 is the default on Ubuntu 24.04. On 22.04, add `ppa:deadsnakes/ppa` first, or install
  it with [pyenv](https://github.com/pyenv/pyenv)
  (`pyenv install`, which reads `.python-version`) or [uv](https://docs.astral.sh/uv/).
- Node 24: use [nvm](https://github.com/nvm-sh/nvm), then run `nvm install` (it reads `.nvmrc`).
- Docker Engine and the compose plugin: <https://docs.docker.com/engine/install/ubuntu/>, then
  `sudo usermod -aG docker $USER` and log out and back in.

Not sure what you have? After cloning, run **`npm run doctor`**. It checks everything and prints
an install hint for whatever is missing.

---

## Quick start (Docker, recommended)

```bash
git clone <repo-url> fourierlearn
cd fourierlearn
docker compose up --build
```

The first build takes a while because it downloads LaTeX. When it's done:

- App: <http://localhost:3000>. The status panel should show everything green.
- API health: <http://localhost:8000/api/health>
- API docs (Swagger): <http://localhost:8000/docs>
- Postgres: `localhost:5433`, user/password/db `fourierlearn`

Source folders are mounted into the containers, so edits hot-reload. `node_modules`, the Python
venv and `.next` live in their own Docker volumes, so they never clash with a native install on
your machine. If `requirements*.txt` or `package-lock.json` change, the containers reinstall the
dependencies automatically on the next start.

Useful commands:

```bash
docker compose up --build -d                                  # run in the background
docker compose logs -f backend                                # follow logs
docker compose exec backend python scripts/manim_smoke.py     # Manim smoke test inside Docker
docker compose exec backend python -m pytest                  # backend tests inside Docker
docker compose exec backend alembic upgrade head              # migrations inside Docker
docker compose exec backend python -m app.db.seed             # load backend/content/ into the db
docker compose logs -f worker                                 # follow the render worker
docker compose down                                           # stop (database data is kept)
docker compose down -v                                        # stop and DELETE all volumes (db data, deps)
```

The smoke test writes its video to `backend/media/smoke/videos/480p15/SmokeScene.mp4` on your
machine.

## Quick start (native)

```bash
git clone <repo-url> fourierlearn
cd fourierlearn
npm run setup     # one-time: venv, Python + npm deps, .env files
npm run doctor    # optional: see what's missing
npm run dev       # Postgres (via Docker if available) + backend + frontend
```

`npm run setup` creates `backend/.venv`, installs `requirements.txt` and `requirements-dev.txt`,
runs `npm install` at the root and in `frontend/`, and copies each `.env.example` to `.env` (it
never overwrites an existing `.env`). If Manim can't be installed because Cairo/Pango is missing,
setup installs everything else and tells you. Install the system libraries, then run
`npm run setup` again.

`npm run dev` starts Postgres with `docker compose up -d db` when Docker is running. Otherwise it
prints a warning and the backend uses whatever `DATABASE_URL` is in `backend/.env`, for example a
locally installed Postgres. Logs from both servers are colour-prefixed. **Ctrl+C stops both.**

The app works without Postgres, LaTeX or Manim. `/api/health` just reports those checks as
`false` (red in the UI).

### Running the servers separately

From the repo root: `npm run dev:backend` and `npm run dev:frontend`.

Or by hand:

```bash
# Backend: activate the venv first (see "venv activation" below), then:
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend, in a second terminal:
cd frontend
npm run dev
```

---

## Working as a team

The build plan (what to build, in which order, by whom) is in **[docs/PLAN.md](docs/PLAN.md)**.
Read **[CONTRIBUTING.md](CONTRIBUTING.md)** before your first change. It covers branches, pull
requests, code formatting, adding dependencies and database migrations. Every pull request is
checked automatically by GitHub Actions (`.github/workflows/`).

## Commands

All commands run from the repo root and work on Windows, macOS and Linux.

| Command                     | What it does                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------- |
| `docker compose up --build` | Run the whole stack in Docker (db + backend + frontend) with hot reload               |
| `npm run setup`             | One-time native setup (venv, deps, `.env` files)                                      |
| `npm run dev`               | Start Postgres (Docker), backend and frontend together                                |
| `npm run dev:backend`       | Backend only (`uvicorn --reload` on port 8000)                                        |
| `npm run dev:frontend`      | Frontend only (`next dev` on port 3000)                                               |
| `npm run doctor`            | Check Python, Node, Docker, FFmpeg, LaTeX, espeak-ng, Manim and ports, with fix hints |
| `npm run test`              | Everything CI checks: lint + format check, pytest, frontend type-check                |
| `npm run lint`              | Ruff (Python), ESLint and Prettier checks only                                        |
| `npm run format`            | Auto-format all code (Ruff for Python, Prettier for the rest)                         |
| `npm run deps:lock`         | Regenerate `backend/requirements*.txt` after editing `requirements*.in`               |
| `npm run manim:smoke`       | Render a tiny Manim scene (axes + `y = x^2`) at low quality and print the video path  |
| `npm run db:migrate`        | `alembic upgrade head`                                                                |
| `npm run render -- <file>`  | Render a module request (e.g. `backend/examples/gradient_of_line.L2.render.json`)     |
| `npm run primitives:check`  | Validate every primitive across its parameter grid at all levels (docs/primitives.md) |
| `npm run api:types`         | Regenerate the frontend's API types after changing an API schema (CI checks this)     |
| `npm run db:seed`           | Load the taxonomy, glossary and item bank of `backend/content/` into the database     |
| `npm run worker`            | Start a render worker: renders queued lessons (`-- --once` for a single job)          |

The npm scripts call `backend/.venv`'s Python directly, so you don't need to activate the venv for
them.

## Configuration

Every setting comes from environment variables or `.env` files. Real `.env` files are git-ignored,
and only the `.env.example` files are committed.

| File            | Variables                                                                                                                                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.env` (root)   | `FRONTEND_PORT` (3000), `BACKEND_PORT` (8000), `POSTGRES_PORT` (5433), Postgres credentials, `DOCKER_FILE_POLLING`                                                                                                     |
| `backend/.env`  | `DATABASE_URL`, `CORS_ORIGINS`, `MEDIA_DIR`, `TTS_PROVIDER`, `TTS_MODEL_DIR`, `RENDER_QUALITY`, `RENDER_WORKERS`, `STUB_API`, `STUB_LATENCY_MS`, `SESSION_COOKIE_SECURE`, `LLM_API_KEY` / `TTS_API_KEY` (not used yet) |
| `frontend/.env` | `BACKEND_URL` (where the Next.js server forwards `/api` and `/media`)                                                                                                                                                  |

The browser only talks to the Next.js app. Next.js forwards `/api/*` and `/media/*` to the
backend (`frontend/next.config.ts`), so the session cookie works without CORS. Open the app at
`http://localhost:3000`, not `127.0.0.1`.

If you change a port in the root `.env`, also update `DATABASE_URL` and `CORS_ORIGINS` in
`backend/.env` and `BACKEND_URL` in `frontend/.env` (`npm run dev` passes the right `BACKEND_URL`
to the frontend for you). Docker Compose derives these from the root `.env` automatically.

`MEDIA_DIR` (default `backend/media`) is created on startup and is git-ignored. Rendered modules
go to `media/variants/<cache key>/`, narration clips to `media/tts/`, compiled formulas to
`media/tex/`.

## Rendering a module

```bash
npm run render -- backend/examples/gradient_of_line.L2.render.json
```

This renders the example module (gradient of a straight line, Level 2) and prints where it was
stored and how long each stage took. Then start the app (`npm run dev` or Docker) and open
<http://localhost:3000/dev/modules> to play it with its captions and concept chips. A second
render of the same request comes from the cache; add `--force` to render again. Options:
`--tts kokoro|espeak|fake` (`fake` is silent narration and needs no voice),
`--quality 480p30|720p30|1080p30`, `--workers N`.

The default voice is Kokoro, a free, local neural voice (Apache 2.0). Its model files (about
350 MB) are downloaded into `backend/models/kokoro/` the first time you render, and that folder is
git-ignored. espeak-ng is still available as `--tts espeak`.

If a render stops with `BrokenProcessPool` or `OpenBLAS error: Memory allocation still failed`,
the machine is short of memory: close other apps, or render with `--workers 1` and the environment
variable `OPENBLAS_NUM_THREADS=1`.

How the engine works is described in `backend/app/renderer/engine.py`; measured render times are
in [docs/benchmarks.md](docs/benchmarks.md), and how to write a primitive in
[docs/primitives.md](docs/primitives.md).

## Lessons through the queue (Phase 3)

A hand-written lesson can now be rendered the way generated lessons will be: stored in Postgres,
queued, rendered by a worker in the background, and played through the normal lesson endpoints,
starting as soon as its first beat is ready. Until the planner exists (Phase 4), the lesson is
written by hand: a scene plan per module with the primitive parameters and narration at one or
more levels. `backend/examples/gradient_of_line.lesson.json` is a two-module example.

```bash
npm run db:migrate          # create the tables (once, and after pulling new migrations)
npm run db:seed             # load backend/content/ (safe to run again)
npm run dev                 # Postgres, backend and frontend
npm run worker              # in a second terminal: renders queued lessons
```

Then, in <http://localhost:8000/docs>:

1. **Log in.** Use `POST /api/auth/login` with `student@fourierlearn.test` / `password123`.
2. **Submit the lesson.** `POST /api/dev/render` with the contents of
   `backend/examples/gradient_of_line.lesson.json` returns a `lesson_id`. A 422 lists every
   problem found: an unknown primitive, glossary term or check item, or beats that don't match
   the plan.
3. **Follow it.** `GET /api/lessons/{lesson_id}/current-module` turns from `preparing` to `ready`
   once the first beat is rendered. `GET /api/lessons/{lesson_id}/events` streams each beat as it
   is ready.

Or check the whole path at once: `cd backend && .venv/bin/python scripts/check_dev_lesson.py`
(Windows: `.venv\Scripts\python`). Add `--lesson examples/gradient_of_curve.lesson.json` to
run the second example, a three-module calculus lesson (secant to tangent, the gradient function
of $x^2$, stationary points) built with SecantToTangent, TangentSlide and EquationTransform.

How it works:

- **The render queue** is a Postgres table (`app/scheduler/queue.py`). Workers take jobs by
  priority with `SELECT … FOR UPDATE SKIP LOCKED`, so you can run several. Each job gets three
  attempts, logged on the job.
- **The variant cache** is checked first: a variant already rendered, or being rendered for
  another lesson, is reused. The cache key includes the voice engine, so a Kokoro video is never
  served where espeak-ng was asked for.
- **Ids decide who answers.** Lessons made this way have ids from 1 and are served from the
  database. The stub's lessons have ids from 1,000,000, so the two live side by side and the
  frontend uses both through the same endpoints.

## The stub API (Phase 2)

During Phase 2 every endpoint of the API catalogue ([docs/frontend.md §7](docs/frontend.md#7-api-catalogue))
is served by an in-memory stub (`backend/app/stub/`), so the frontend can be built before the
planner, render queue and learner model exist. It needs no Postgres, LaTeX, Manim or voice model.
Stub responses carry the header `X-FourierLearn-Stub: 1`, and all stub data resets when the backend
restarts.

- **Browse the API** at <http://localhost:8000/docs>. The request and response shapes are in
  `backend/app/api/schemas/`.
- **Stub-only test accounts.** All three use the password `password123`:
  - `student@fourierlearn.test`: has lessons in progress, completed and in study mode
  - `new@fourierlearn.test`: hasn't done the diagnostic
  - `admin@fourierlearn.test`: the admin
- **Lessons:** a query mentioning gradient, slope or line starts a three-module lesson. Anything
  else gets the out-of-scope reply.
- **Test words in the query:**
  - `test:slow`: the first module takes 60 s
  - `test:fail`: module 2 fails with the glossary fallback
  - `test:static`: a study-mode lesson
- **The videos** are the example module at Level 1, 2 and 3, committed in `backend/fixtures/variants/`
  and copied into `media/variants/` when the backend starts.
- **Checking the event logger:** `GET /api/dev/events` lists the events your account has sent.
- **After changing a schema** in `backend/app/api/schemas/`, run `npm run api:types` and commit
  `frontend/src/lib/api/openapi.json` and `schema.d.ts`. The frontend's types are generated from
  them, and CI fails if they are out of date.

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, CORS, router registration
│   │   ├── core/config.py         # settings from env / backend/.env (pydantic-settings)
│   │   ├── db/                    # engine, session, Base, models of the data dictionary
│   │   ├── api/routes/            # every /api endpoint (docs/frontend.md §7)
│   │   ├── api/schemas/           # request and response bodies: the API's contract with the frontend
│   │   ├── stub/                  # Phase 2: in-memory stub behind the API, with seed data
│   │   ├── lessons/               # lessons stored in the database, played through the same API
│   │   ├── content.py             # loads and checks backend/content/ (taxonomy, glossary, items)
│   │   ├── prompt_interpreter/    # scene-plan reference check now; the LLM planner in Phase 4
│   │   ├── contracts/             # data shapes shared by all components (docs/contracts.md)
│   │   ├── code_generator/        # placeholder: scene plan → primitive parameters (no free code)
│   │   ├── primitives/            # validated Manim primitives, SymPy checks, harness
│   │   ├── renderer/              # render engine: beats → narrated, cached module video
│   │   ├── audio_pipeline/        # TTS (Kokoro, espeak-ng, fake); narration scripts come in Phase 4
│   │   ├── scheduler/             # the render queue (queue.py); prefetching comes in Phase 5
│   │   ├── learner_state/         # placeholder: Bayesian Knowledge Tracing
│   │   └── workers/               # render workers: npm run worker
│   ├── alembic/ + alembic.ini     # migrations; URL comes from DATABASE_URL
│   ├── examples/                  # example scene plan and render requests at L1, L2, L3
│   ├── content/                   # teaching content as data: concepts, glossary, item bank
│   ├── fixtures/variants/         # the example module rendered at L1, L2, L3 (the stub's videos)
│   ├── scripts/manim_smoke.py     # Manim + LaTeX + FFmpeg smoke test
│   ├── scripts/export_openapi.py  # writes the OpenAPI document for npm run api:types
│   ├── scripts/check_dev_lesson.py # end-to-end check of the queue path (milestone M2)
│   ├── tests/                     # pytest (no database needed)
│   ├── requirements.in            # direct runtime deps (edit this)
│   ├── requirements.txt           # generated lockfile: every package pinned, all OSes
│   ├── requirements-dev.in/.txt   # pytest, ruff, httpx, uv (same pattern)
│   ├── pyproject.toml             # ruff + pytest config
│   ├── Dockerfile + docker-entrypoint.sh
│   └── .env.example
├── frontend/
│   ├── src/app/page.tsx           # home page with the status panel
│   ├── src/app/dev/modules/       # developer viewer for rendered modules
│   ├── src/lib/contracts.ts       # TypeScript mirror of the manifest (to be replaced by api/)
│   ├── src/lib/api/               # generated OpenAPI document and TypeScript types
│   ├── next.config.ts             # forwards /api and /media to the backend
│   ├── Dockerfile + docker-entrypoint.sh
│   └── .env.example
├── scripts/                       # cross-platform Node helpers used by package.json
│   ├── setup.mjs  dev.mjs  doctor.mjs
│   ├── run.mjs                    # runs backend/frontend tasks with the right venv paths
│   └── lib.mjs                    # shared helpers
├── .github/                       # CI workflows + pull request template
├── docker-compose.yml
├── package.json                   # root scripts (+ concurrently, prettier)
├── docs/                          # plan, contracts, writing primitives, benchmarks
├── CONTRIBUTING.md                # team workflow: branches, PRs, deps, migrations
├── .env.example                   # ports + Postgres credentials
├── .nvmrc  .python-version        # pinned Node / Python versions
└── .gitattributes  .editorconfig  .gitignore  .prettierrc.json
```

Versions are pinned exactly: full lockfiles in `backend/requirements*.txt` (generated from the
`.in` files by `npm run deps:lock`), exact versions plus `package-lock.json`
for npm (`save-exact=true` in `.npmrc`), and exact Docker image tags.

---

## Troubleshooting

**A port is already in use (3000 / 8000 / 5433).**
`npm run doctor` shows which ports are taken. Find the process with `lsof -i :8000`
(macOS/Linux) or `netstat -ano | findstr :8000` (Windows), then stop it. You can also change the
port in the root `.env` (and the matching URLs, see [Configuration](#configuration)). An old
`docker compose` stack is a common cause, so try `docker compose down`. Postgres uses host port
5433 so it doesn't clash with a local Postgres on 5432.

**`/api/health` shows `manim: false`.**
Natively, Manim needs Cairo and Pango to install. On macOS run `brew install cairo pango pkg-config`.
On Ubuntu run `sudo apt install build-essential pkg-config libcairo2-dev libpango1.0-dev`. Then
run `npm run setup` again. Or use Docker, where it's preinstalled.

**`/api/health` shows `latex: false`, or MathTex fails.**
The check needs both `latex` and `dvisvgm` on your PATH. Install MiKTeX/TeX Live (Windows),
MacTeX/BasicTeX (macOS) or the `texlive-*` + `dvisvgm` packages (Ubuntu), then **open a new
terminal** so the PATH updates. On MiKTeX, allow on-the-fly package installs. The first MathTex
render may pause while packages download.

**`/api/health` shows `ffmpeg: false`.** Install FFmpeg (see Prerequisites) and open a new terminal.

**`/api/health` shows `database: false`.** Postgres isn't running or `DATABASE_URL` is wrong.
Run `docker compose up -d db`, then check `DATABASE_URL` in `backend/.env` (it uses port 5433).

**Windows line endings / `sh: docker-entrypoint.sh: not found` / `\r` errors in containers.**
`.gitattributes` forces LF line endings, so a fresh clone is fine. If your working copy still has
CRLF files, commit or stash your changes first (the next command discards uncommitted work), then:
`git config core.autocrlf false && git rm --cached -r -q . && git reset --hard`.
Make sure your editor saves files with LF (`.editorconfig` asks it to).

**Hot reload doesn't notice changes in Docker (mostly Windows).**
Keep the repo inside the WSL2 filesystem (e.g. `\\wsl$\Ubuntu\home\<you>\fourierlearn`), not
under `C:\`. Or set `DOCKER_FILE_POLLING=true` in the root `.env` and restart the stack.

**Activating the venv** (only needed when you run commands by hand; the npm scripts don't need it):

| OS / shell         | Command                                 |
| ------------------ | --------------------------------------- |
| Windows PowerShell | `backend\.venv\Scripts\Activate.ps1`    |
| Windows cmd        | `backend\.venv\Scripts\activate.bat`    |
| Windows Git Bash   | `source backend/.venv/Scripts/activate` |
| macOS / Linux      | `source backend/.venv/bin/activate`     |

If PowerShell refuses to run `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. Leave the venv with `deactivate`.

**`npm run setup` says Python 3.12 was not found.** Install Python 3.12 (see Prerequisites) and
open a new terminal. On Windows, check that `py -3.12 --version` works. Elsewhere, check
`python3.12 --version`.

**Strange dependency errors in Docker.** Reset the dependency volumes with `docker compose down -v`
(this also deletes the local database), then `docker compose up --build`.
