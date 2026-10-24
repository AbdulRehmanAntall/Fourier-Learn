# Working on FourierLearn

How the three of us work on this repo, so that `main` always runs and nobody's work gets lost.
Setup instructions are in the [README](README.md).

## The golden rules

1. **Never push straight to `main`.** `main` must always work.
2. **One branch per piece of work**, then a **pull request (PR)**.
3. **A teammate reviews the PR** before it's merged.
4. **CI must be green** (the ✓ on the PR) before merging.
5. **Never commit secrets.** API keys and passwords go in `.env` files only. Those are git-ignored;
   share values privately.

## Day-to-day workflow

```bash
git switch main
git pull                               # get everyone's latest work
npm run setup                          # only if dependencies changed (safe to run anytime)
git switch -c feature/bkt-model        # new branch for your task

# ... write code ...

npm run format                         # auto-format Python + TypeScript
npm run test                           # lint, format check, tests, type check
git add -A
git commit -m "feat: add BKT update step"
git push -u origin feature/bkt-model
```

Then open the PR on GitHub, fill in the checklist, and ask a teammate to review. After it's merged,
delete the branch (GitHub offers a button) and start the next task from an updated `main`.

If `main` changed while you were working: `git switch main && git pull`, then
`git switch your-branch && git merge main`, fix any conflicts, run `npm run test`, push.

### Branch names

| Prefix     | For                           | Example                      |
| ---------- | ----------------------------- | ---------------------------- |
| `feature/` | new functionality             | `feature/prompt-interpreter` |
| `fix/`     | bug fixes                     | `fix/health-timeout`         |
| `chore/`   | tooling, dependencies, config | `chore/update-manim`         |
| `docs/`    | documentation only            | `docs/setup-windows`         |

### Commit messages

Start with a type, then say what changed in a few words:
`feat:` (new feature), `fix:` (bug fix), `chore:` (tooling/deps), `docs:`, `test:`, `refactor:`.
Example: `fix: return 503 when the render queue is full`.

Small commits with clear messages make reviews and bug hunts much easier.

## Code style

You don't need to think about formatting: `npm run format` does it.

- Python: [Ruff](https://docs.astral.sh/ruff/) (lint + format), settings in `backend/pyproject.toml`.
- TypeScript/JSON/Markdown/YAML: [Prettier](https://prettier.io/) (`.prettierrc.json`) and ESLint.
- CI fails if code isn't formatted, so run `npm run format` before committing.
- VS Code will suggest the matching extensions (`.vscode/extensions.json`). With them installed,
  turn on "Format on Save".

## Dependencies

**Python.** Edit the short lists, never the generated files:

1. Add or change the package in `backend/requirements.in` (or `requirements-dev.in` for test/dev
   tools), pinned with `==`.
2. Run `npm run deps:lock`. This regenerates `requirements.txt` / `requirements-dev.txt`, which pin
   _every_ package (including indirect ones) for Windows, macOS and Linux.
3. Run `npm run setup` to install, then commit the `.in` **and** `.txt` files together.

CI checks that the `.txt` files match the `.in` files.

**npm.** From `frontend/` (or the root, for tooling): `npm install some-package`. Exact versions are
saved automatically (`.npmrc`). Commit `package.json` **and** `package-lock.json` together.

Teammates pick up dependency changes with `npm run setup`. Docker picks them up automatically on
the next `docker compose up`.

## Database changes

Never change the database by hand. Use an Alembic migration so everyone's database stays in sync:

```bash
cd backend
# activate the venv first (see README), then:
alembic revision --autogenerate -m "add learner table"
```

Review the generated file in `backend/alembic/versions/` (autogenerate isn't perfect: it misses
check constraints and server defaults for new NOT NULL columns), commit it with your model
changes, and teammates run `npm run db:migrate`. A column or table beyond the report's data
dictionary (Table 4.8) must also be listed in `ADDITIONS` in `backend/tests/test_db_models.py`.

**Database tests.** Tests marked `db` need Postgres and are skipped without it. To run them, point
`TEST_DATABASE_URL` at an empty database they may wipe, never your development one:
`TEST_DATABASE_URL=postgresql+psycopg://fourierlearn:fourierlearn@localhost:5433/fourierlearn_test
npm run test:backend` (create `fourierlearn_test` first). CI always runs them.

**Teaching content** (concepts, glossary, check questions) lives in `backend/content/` as JSON,
not in code. After editing it, run `npm run db:seed`; the tests check the content for mistakes
such as a prerequisite cycle or an answer that is not one of the options.
Never edit a migration that's already merged into `main`. Add a new one instead.

## Where code goes

Each future component has its own package under `backend/app/` (see the README's project
structure). Keep each one focused on its job, and talk to the others through clear functions or
API routes. New endpoints go in `backend/app/api/routes/` and are registered in `app/main.py`.
Add tests in `backend/tests/` for anything with logic, especially the BKT maths.

## Automated checks (CI)

GitHub Actions runs automatically, and the results show on every PR:

- **CI** (every PR, ~2 min): Ruff lint and format, lockfile check, pytest, ESLint, Prettier, and
  type check.
- **Full check** (pushes to `main`, and PRs that change setup/Docker/dependency files): runs
  `npm run setup` on Windows, macOS and Linux, and starts the full Docker stack, checking that
  `/api/health` reports everything green and Manim renders a video.

If a check fails, open it on the PR to see the log, fix the problem, and push again.

## Protecting `main` (one-time, repo owner)

GitHub → **Settings → Branches → Add branch ruleset** (or "Add rule") for `main`:

- Require a pull request before merging (1 approval).
- Require status checks to pass: select **Backend (lint, format, tests)** and
  **Frontend (lint, format, types)**. They appear in the list after CI has run once.
- Block force pushes.
