// Task runner used by the root package.json scripts, e.g. `node scripts/run.mjs backend:dev`.
// Runs backend tasks with the venv's Python, so no venv activation is needed.
import { BACKEND, FRONTEND, NPM, VENV_PYTHON, fail, requireVenv, rootConfig, run } from "./lib.mjs";

const { backendPort, frontendPort } = rootConfig();

const python = (args) => () => {
  requireVenv();
  return run(VENV_PYTHON, args, { cwd: BACKEND });
};

const tasks = {
  "backend:dev": python(["-m", "uvicorn", "app.main:app", "--reload", "--reload-dir", "app", "--port", backendPort]),
  "backend:test": python(["-m", "pytest"]),
  "backend:lint": python(["-m", "ruff", "check", "."]),
  "db:migrate": python(["-m", "alembic", "upgrade", "head"]),
  "manim:smoke": python(["scripts/manim_smoke.py"]),
  "frontend:dev": () => run(NPM, ["run", "dev", "--", "--port", frontendPort], { cwd: FRONTEND }),
};

const name = process.argv[2];
if (!tasks[name]) {
  fail(`Unknown task "${name}". Available: ${Object.keys(tasks).join(", ")}`);
  process.exit(1);
}
process.exitCode = await tasks[name]();
