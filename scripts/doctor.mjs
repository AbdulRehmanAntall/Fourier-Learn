// `npm run doctor`: check the tools FourierLearn needs and print OS-specific install hints.
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { ROOT, VENV_PYTHON, c, capture, fail, isWindows, ok, rootConfig, warn } from "./lib.mjs";

const os = isWindows ? "windows" : process.platform === "darwin" ? "macos" : "linux";
const hint = (byOs) => byOs[os];

const PY_VERSION = readFileSync(path.join(ROOT, ".python-version"), "utf8").trim();
const PY_MINOR = PY_VERSION.split(".").slice(0, 2).join(".");
const NODE_VERSION = readFileSync(path.join(ROOT, ".nvmrc"), "utf8").trim().replace(/^v/, "");

const results = [];
function report(passed, label, detail, fix, { required = false, optional = false } = {}) {
  results.push({ passed, required });
  const text = detail ? `${label} ${c.dim(`(${detail})`)}` : label;
  if (passed) return ok(text);
  (optional ? warn : fail)(text);
  if (fix) console.log(`    ${c.dim("fix:")} ${fix}`);
}

function firstLine(res) {
  return (res.stdout || res.stderr).trim().split(/\r?\n/)[0];
}

console.log(c.bold(`FourierLearn doctor (${os})\n`));

// Python
{
  const venv = existsSync(VENV_PYTHON);
  const res = venv
    ? capture(VENV_PYTHON, ["--version"])
    : isWindows
      ? capture("py", [`-${PY_MINOR}`, "--version"])
      : capture(`python${PY_MINOR}`, ["--version"]);
  const version = res.status === 0 ? firstLine(res).replace("Python ", "") : null;
  report(
    version?.startsWith(`${PY_MINOR}.`),
    `Python ${PY_MINOR}`,
    version
      ? `${version}${venv ? ", backend/.venv" : ", no venv yet: run npm run setup"}`
      : "not found",
    hint({
      windows: `winget install Python.Python.${PY_MINOR} (any ${PY_MINOR}.x is fine)`,
      macos: `brew install python@${PY_MINOR}`,
      linux: `sudo apt install python${PY_MINOR} python${PY_MINOR}-venv, or use pyenv / uv`,
    }),
    { required: true },
  );
}

// Node
{
  const major = process.versions.node.split(".")[0];
  report(
    Number(major) >= Number(NODE_VERSION.split(".")[0]),
    `Node ${NODE_VERSION.split(".")[0]}+ (LTS)`,
    `${process.versions.node}, .nvmrc wants ${NODE_VERSION}`,
    hint({
      windows:
        "install Node LTS from https://nodejs.org/ (or nvm-windows: nvm install " +
        NODE_VERSION +
        ")",
      macos: `nvm install (reads .nvmrc), or brew install node@${NODE_VERSION.split(".")[0]}`,
      linux: "nvm install (reads .nvmrc), see https://github.com/nvm-sh/nvm",
    }),
    { required: true },
  );
}

// Docker (optional for native dev, required for the containerised workflow)
{
  const cli = capture("docker", ["--version"]);
  const daemon = cli.status === 0 && capture("docker", ["info"]).status === 0;
  report(
    daemon,
    "Docker (optional)",
    cli.status !== 0
      ? "not installed"
      : daemon
        ? firstLine(cli)
        : "installed but the daemon is not running",
    cli.status === 0
      ? "start Docker Desktop (or: sudo systemctl start docker)"
      : hint({
          windows:
            "install Docker Desktop (uses WSL2): https://docs.docker.com/desktop/setup/install/windows-install/",
          macos:
            "install Docker Desktop: https://docs.docker.com/desktop/setup/install/mac-install/",
          linux:
            "install Docker Engine + compose plugin: https://docs.docker.com/engine/install/ubuntu/",
        }),
    { optional: true },
  );
}

// FFmpeg
{
  const res = capture("ffmpeg", ["-version"]);
  report(
    res.status === 0,
    "FFmpeg",
    res.status === 0 ? firstLine(res).split(" ").slice(0, 3).join(" ") : "not found",
    hint({
      windows: "winget install Gyan.FFmpeg (then open a new terminal)",
      macos: "brew install ffmpeg",
      linux: "sudo apt install ffmpeg",
    }),
  );
}

// LaTeX (latex + dvisvgm are what Manim's MathTex uses)
{
  const latex = capture("latex", ["--version"]);
  const dvisvgm = capture("dvisvgm", ["--version"]);
  report(
    latex.status === 0 && dvisvgm.status === 0,
    "LaTeX (latex + dvisvgm)",
    [
      latex.status === 0 ? "latex ok" : "latex missing",
      dvisvgm.status === 0 ? "dvisvgm ok" : "dvisvgm missing",
    ].join(", "),
    hint({
      windows:
        "install MiKTeX (https://miktex.org/download) and allow on-the-fly package installs, or TeX Live",
      macos: "brew install --cask mactex-no-gui   (smaller: brew install --cask basictex)",
      linux:
        "sudo apt install texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-science cm-super dvisvgm",
    }),
  );
}

// Manim
{
  const venv = existsSync(VENV_PYTHON);
  const res = venv ? capture(VENV_PYTHON, ["-c", "import manim; print(manim.__version__)"]) : null;
  report(
    res?.status === 0,
    "Manim importable",
    !venv ? "no venv yet" : res.status === 0 ? `manim ${res.stdout.trim()}` : "import failed",
    !venv
      ? "run npm run setup"
      : hint({
          windows: "re-run npm run setup (Windows wheels include Cairo/Pango)",
          macos: "brew install cairo pango pkg-config, then npm run setup",
          linux:
            "sudo apt install build-essential pkg-config libcairo2-dev libpango1.0-dev, then npm run setup",
        }),
  );
}

// Ports
function portFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(Number(port));
  });
}

const { frontendPort, backendPort, postgresPort } = rootConfig();
for (const [port, what] of [
  [frontendPort, "frontend"],
  [backendPort, "backend"],
  [postgresPort, "postgres"],
]) {
  const free = await portFree(port);
  report(
    free,
    `Port ${port} (${what})`,
    free ? "free" : "in use, maybe FourierLearn is already running",
    `stop whatever uses it (${isWindows ? `netstat -ano | findstr :${port}` : `lsof -i :${port}`}) or change the port in the root .env`,
    { optional: true },
  );
}

const failed = results.filter((r) => !r.passed);
console.log("");
if (failed.length === 0) console.log(c.green(c.bold("All checks passed.")));
else
  console.log(
    `${failed.length} check(s) need attention. The app still starts without FFmpeg/LaTeX/Manim/Postgres.`,
  );
process.exitCode = results.some((r) => r.required && !r.passed) ? 1 : 0;
