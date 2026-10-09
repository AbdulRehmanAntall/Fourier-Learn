// `npm run dev`: start Postgres (via Docker, if available), then backend + frontend together.
import path from "node:path";
import concurrently from "concurrently";
import { BACKEND, ROOT, c, dockerAvailable, ok, readEnvFile, requireVenv, rootConfig, run, step, warn } from "./lib.mjs";

requireVenv();
const { backendPort, frontendPort } = rootConfig();

step("Database");
if (dockerAvailable()) {
  // --wait blocks until the db healthcheck passes.
  const code = await run("docker", ["compose", "up", "-d", "--wait", "db"], { cwd: ROOT });
  if (code === 0) ok("Postgres is running (docker compose service `db`)");
  else warn("Could not start Postgres with Docker. Continuing; /api/health will show database=false.");
} else {
  const dbUrl = readEnvFile(path.join(BACKEND, ".env")).DATABASE_URL ?? "(not set)";
  warn("Docker is not available, so Postgres was not started.");
  warn(`Using DATABASE_URL from backend/.env: ${dbUrl.replace(/\/\/([^:]+):[^@]*@/, "//$1:***@")}`);
}

step(`Starting backend (:${backendPort}) and frontend (:${frontendPort}). Press Ctrl+C to stop.`);
console.log(`  API:      ${c.cyan(`http://localhost:${backendPort}/api/health`)}`);
console.log(`  API docs: ${c.cyan(`http://localhost:${backendPort}/docs`)}`);
console.log(`  App:      ${c.cyan(`http://localhost:${frontendPort}`)}\n`);

const { result } = concurrently(
  [
    { command: "node scripts/run.mjs backend:dev", name: "backend", prefixColor: "blue" },
    { command: "node scripts/run.mjs frontend:dev", name: "frontend", prefixColor: "magenta" },
  ],
  { cwd: ROOT, prefix: "name", killOthersOn: ["failure", "success"], restartTries: 0 },
);

result.then(
  () => process.exit(0),
  () => process.exit(1),
);
