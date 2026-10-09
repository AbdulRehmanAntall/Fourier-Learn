// Task runner used by the root package.json scripts, e.g. `node scripts/run.mjs backend:dev`.
// Runs backend tasks with the venv's Python, so no venv activation is needed.
import { readFileSync } from "node:fs";
import path from "node:path";
import {
  BACKEND,
  FRONTEND,
  NPM,
  ROOT,
  VENV_PYTHON,
  fail,
  requireVenv,
  rootConfig,
  run,
} from "./lib.mjs";

const { backendPort, frontendPort } = rootConfig();
const PY_MINOR = readFileSync(path.join(ROOT, ".python-version"), "utf8")
  .trim()
  .split(".")
  .slice(0, 2)
  .join(".");

/** Run Python commands from backend/ in order, stopping at the first failure. */
const python =
  (...commands) =>
  async () => {
    requireVenv();
    for (const args of commands) {
      const code = await run(VENV_PYTHON, args, { cwd: BACKEND });
      if (code !== 0) return code;
    }
    return 0;
  };

// One lockfile for every OS (--universal), so Windows/macOS/Linux teammates install the same versions.
const lock = (input, output) => [
  "-m",
  "uv",
  "pip",
  "compile",
  "--universal",
  "--python-version",
  PY_MINOR,
  "--no-header",
  "--annotation-style",
  "split",
  "--quiet",
  input,
  "-o",
  output,
];

const tasks = {
  "backend:dev": python([
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--reload-dir",
    "app",
    "--port",
    backendPort,
  ]),
  "backend:test": python(["-m", "pytest"]),
  "backend:lint": python(["-m", "ruff", "check", "."], ["-m", "ruff", "format", "--check", "."]),
  "backend:format": python(["-m", "ruff", "check", "--fix", "."], ["-m", "ruff", "format", "."]),
  "deps:lock": python(
    lock("requirements.in", "requirements.txt"),
    lock("requirements-dev.in", "requirements-dev.txt"),
  ),
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
