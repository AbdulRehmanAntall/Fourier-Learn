// Shared helpers for the root scripts. Plain Node only: no npm packages,
// so setup.mjs can run before anything is installed.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const isWindows = process.platform === "win32";
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const BACKEND = path.join(ROOT, "backend");
export const FRONTEND = path.join(ROOT, "frontend");
export const VENV = path.join(BACKEND, ".venv");
export const VENV_PYTHON = isWindows
  ? path.join(VENV, "Scripts", "python.exe")
  : path.join(VENV, "bin", "python");
export const NPM = isWindows ? "npm.cmd" : "npm";

const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code) => (text) => (useColor ? `\x1b[${code}m${text}\x1b[0m` : String(text));
export const c = { green: paint(32), red: paint(31), yellow: paint(33), cyan: paint(36), bold: paint(1), dim: paint(2) };

export const ok = (msg) => console.log(`${c.green("✓")} ${msg}`);
export const fail = (msg) => console.log(`${c.red("✗")} ${msg}`);
export const warn = (msg) => console.log(`${c.yellow("!")} ${msg}`);
export const step = (msg) => console.log(`\n${c.cyan("→")} ${c.bold(msg)}`);

/** Parse a simple KEY=VALUE .env file. Missing file → {}. */
export function readEnvFile(file) {
  if (!existsSync(file)) return {};
  const env = {};
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
  return env;
}

/** Ports and other root-level settings: process env > root .env > defaults. */
export function rootConfig() {
  const env = { ...readEnvFile(path.join(ROOT, ".env")), ...process.env };
  return {
    frontendPort: env.FRONTEND_PORT || "3000",
    backendPort: env.BACKEND_PORT || "8000",
    postgresPort: env.POSTGRES_PORT || "5433",
  };
}

/**
 * Run a command synchronously and return { status, stdout, stderr }.
 * On Windows, .cmd/.bat shims (npm.cmd) need a shell, so that case is quoted by hand.
 */
export function capture(cmd, args = [], opts = {}) {
  const needsShell = isWindows && /\.(cmd|bat)$/i.test(cmd);
  const res = needsShell
    ? spawnSync([cmd, ...args].map(quote).join(" "), { shell: true, encoding: "utf8", ...opts })
    : spawnSync(cmd, args, { encoding: "utf8", ...opts });
  return {
    status: res.error ? null : res.status,
    stdout: res.stdout ?? "",
    stderr: res.stderr ?? "",
    error: res.error,
  };
}

/** Run a command with inherited stdio; resolves to its exit code. */
export function run(cmd, args = [], opts = {}) {
  const needsShell = isWindows && /\.(cmd|bat)$/i.test(cmd);
  return new Promise((resolve) => {
    const child = needsShell
      ? spawn([cmd, ...args].map(quote).join(" "), { shell: true, stdio: "inherit", ...opts })
      : spawn(cmd, args, { stdio: "inherit", ...opts });
    child.on("error", (err) => {
      fail(`Could not start ${cmd}: ${err.message}`);
      resolve(1);
    });
    child.on("exit", (code, signal) => resolve(signal ? 1 : (code ?? 1)));
  });
}

function quote(arg) {
  return /[\s"&|<>^]/.test(arg) ? `"${arg.replace(/"/g, '\\"')}"` : arg;
}

/** True if `cmd <versionArg>` runs successfully. */
export function hasCommand(cmd, versionArg = "--version") {
  return capture(cmd, [versionArg]).status === 0;
}

/** True if a Docker daemon is reachable and `docker compose` works. */
export function dockerAvailable() {
  return capture("docker", ["info"]).status === 0 && capture("docker", ["compose", "version"]).status === 0;
}

export function requireVenv() {
  if (!existsSync(VENV_PYTHON)) {
    fail(`Python venv not found at ${path.relative(ROOT, VENV_PYTHON)}. Run ${c.bold("npm run setup")} first.`);
    process.exit(1);
  }
}
