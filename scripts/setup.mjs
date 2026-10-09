// One-time native setup: `npm run setup`.
// Creates backend/.venv, installs Python + npm deps, and copies .env.example → .env.
import { copyFileSync, existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  BACKEND,
  FRONTEND,
  NPM,
  ROOT,
  VENV,
  VENV_PYTHON,
  c,
  capture,
  fail,
  isWindows,
  ok,
  run,
  step,
  warn,
} from "./lib.mjs";

const PY_VERSION = readFileSync(path.join(ROOT, ".python-version"), "utf8").trim(); // e.g. 3.12.15
const PY_MINOR = PY_VERSION.split(".").slice(0, 2).join("."); // e.g. 3.12

/** Find a Python interpreter of the pinned minor version: the Windows `py` launcher first, then common names. */
function findPython() {
  const candidates = isWindows
    ? [
        ["py", [`-${PY_MINOR}`]],
        ["python", []],
        ["python3", []],
      ]
    : [
        [`python${PY_MINOR}`, []],
        ["python3", []],
        ["python", []],
      ];
  for (const [cmd, pre] of candidates) {
    const res = capture(cmd, [...pre, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]);
    if (res.status === 0 && res.stdout.trim() === PY_MINOR) return [cmd, pre];
  }
  return null;
}

async function main() {
  console.log(c.bold("FourierLearn setup"));

  step(`Python ${PY_MINOR} virtual environment (backend/.venv)`);
  if (existsSync(VENV_PYTHON)) {
    // Rebuild a venv made with another Python version (e.g. before .python-version changed).
    const res = capture(VENV_PYTHON, ["-c", "import sys; print('%d.%d' % sys.version_info[:2])"]);
    const venvMinor = res.status === 0 ? res.stdout.trim() : "unknown";
    if (venvMinor !== PY_MINOR) {
      warn(`backend/.venv uses Python ${venvMinor}, not ${PY_MINOR}. Recreating it...`);
      rmSync(VENV, { recursive: true, force: true });
    }
  }
  if (existsSync(VENV_PYTHON)) {
    ok("backend/.venv already exists");
  } else {
    const python = findPython();
    if (!python) {
      fail(
        `Python ${PY_MINOR} not found. Install any Python ${PY_MINOR}.x (see README → Prerequisites), open a new terminal and re-run.`,
      );
      if (isWindows) console.log(`    ${c.dim("fix:")} winget install Python.Python.${PY_MINOR}`);
      process.exit(1);
    }
    const [cmd, pre] = python;
    if ((await run(cmd, [...pre, "-m", "venv", VENV])) !== 0) {
      fail("Could not create the virtual environment.");
      process.exit(1);
    }
    ok("Created backend/.venv");
  }

  step("Python dependencies");
  await run(VENV_PYTHON, ["-m", "pip", "install", "--upgrade", "pip"], { cwd: BACKEND });
  const pipArgs = ["-m", "pip", "install", "-r", "requirements.txt", "-r", "requirements-dev.txt"];
  let manimMissing = false;
  if ((await run(VENV_PYTHON, pipArgs, { cwd: BACKEND })) !== 0) {
    // Usually Manim failing to build pycairo/manimpango because Cairo/Pango aren't installed.
    // Install everything else so the app still runs; /api/health will report manim=false.
    warn(
      "Full install failed (usually Manim: Cairo/Pango system libraries missing). Retrying without Manim...",
    );
    // Install the direct deps minus manim, pinned to the lockfile versions via -c (constraints),
    // so manim's own dependencies (pycairo, manimpango, ...) are skipped too.
    const reqs = readFileSync(path.join(BACKEND, "requirements.in"), "utf8")
      .split(/\r?\n/)
      .filter((line) => !/^\s*manim\b/i.test(line))
      .join("\n");
    const tmpReqs = path.join(tmpdir(), "fourierlearn-requirements-no-manim.txt");
    writeFileSync(tmpReqs, reqs);
    const code = await run(
      VENV_PYTHON,
      [
        "-m",
        "pip",
        "install",
        "-r",
        tmpReqs,
        "-c",
        "requirements.txt",
        "-r",
        "requirements-dev.txt",
      ],
      { cwd: BACKEND },
    );
    rmSync(tmpReqs, { force: true });
    if (code !== 0) {
      fail("pip install failed. See the output above.");
      process.exit(1);
    }
    manimMissing = true;
  }
  ok(
    manimMissing
      ? "Python dependencies installed (without Manim)"
      : "Python dependencies installed",
  );

  step("npm dependencies");
  for (const [dir, label] of [
    [ROOT, "root"],
    [FRONTEND, "frontend"],
  ]) {
    if ((await run(NPM, ["install", "--no-audit", "--no-fund"], { cwd: dir })) !== 0) {
      fail(`npm install failed in ${label}.`);
      process.exit(1);
    }
    ok(`npm install (${label})`);
  }

  step(".env files");
  for (const dir of [ROOT, BACKEND, FRONTEND]) {
    const example = path.join(dir, ".env.example");
    const target = path.join(dir, ".env");
    const rel = path.relative(ROOT, target) || ".env";
    if (existsSync(target)) {
      ok(`${rel} already exists (left unchanged)`);
    } else if (existsSync(example)) {
      copyFileSync(example, target);
      ok(`Created ${rel} from .env.example`);
    }
  }

  console.log(`\n${c.green(c.bold("Setup complete."))}`);
  if (manimMissing) {
    warn(
      `Manim is not installed. Install Cairo/Pango (see README), then run ${c.bold("npm run setup")} again.`,
    );
  }
  console.log(
    `Next: ${c.bold("npm run doctor")} to check system tools, then ${c.bold("npm run dev")}.`,
  );
}

main();
