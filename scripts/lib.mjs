// Shared helpers for the root npm scripts. No dependencies — plain Node.
// Tools are spawned without a shell and never via node_modules/.bin/*.cmd,
// because the '&' in the repo path breaks cmd.exe shims on Windows.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const BACKEND = join(ROOT, "backend");
export const FRONTEND = join(ROOT, "frontend");
export const IS_WIN = process.platform === "win32";
export const VENV_PY = IS_WIN
  ? join(BACKEND, ".venv", "Scripts", "python.exe")
  : join(BACKEND, ".venv", "bin", "python");
export const VITE = join(FRONTEND, "node_modules", "vite", "bin", "vite.js");
export const TSC = join(FRONTEND, "node_modules", "typescript", "bin", "tsc");

const color = (code) => (s) => (process.stdout.isTTY ? `\x1b[${code}m${s}\x1b[0m` : s);
export const c = { cyan: color(36), magenta: color(35), green: color(32), yellow: color(33), red: color(31), dim: color(2) };

export function log(msg) {
  console.log(`${c.green("›")} ${msg}`);
}

export function fail(msg) {
  console.error(`${c.red("✖")} ${msg}`);
  process.exit(1);
}

/** Run a command to completion, inheriting stdio. Exits the process on failure. */
export function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (r.error) fail(`${cmd}: ${r.error.message}`);
  if (r.status !== 0) fail(`${cmd} ${args.join(" ")} exited with ${r.status}`);
}

/** Run npm without relying on the npm.cmd shim when we were launched by npm. */
export function npm(args, cwd) {
  const cli = process.env.npm_execpath;
  if (cli && cli.endsWith(".js")) run(process.execPath, [cli, ...args], { cwd });
  else run(IS_WIN ? "npm.cmd" : "npm", args, { cwd, shell: IS_WIN });
}

/** Find a Python >= 3.11 to create the venv with. */
export function findPython() {
  const candidates = IS_WIN
    ? [["py", ["-3.12"]], ["py", ["-3.13"]], ["py", ["-3.11"]], ["py", ["-3"]], ["python", []]]
    : [["python3.12", []], ["python3", []], ["python", []]];
  for (const [cmd, pre] of candidates) {
    const r = spawnSync(cmd, [...pre, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"], { encoding: "utf8" });
    if (r.status !== 0) continue;
    const [maj, min] = r.stdout.trim().split(".").map(Number);
    if (maj === 3 && min >= 11) return { cmd, pre, version: `${maj}.${min}` };
  }
  return null;
}

/** Long-running child with prefixed output. */
export function startProc(name, paint, cmd, args, cwd) {
  const env = { ...process.env, PYTHONUNBUFFERED: "1" };
  if (!env.NO_COLOR) env.FORCE_COLOR = "1";
  const child = spawn(cmd, args, { cwd, env });
  const prefix = paint(`[${name}]`.padEnd(6));
  for (const stream of [child.stdout, child.stderr]) {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const line of lines) console.log(`${prefix} ${line}`);
    });
  }
  return child;
}

/** Kill a process and its children (uvicorn --reload spawns a worker). */
export function killTree(child) {
  if (!child || child.exitCode !== null) return;
  if (IS_WIN) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  else child.kill("SIGTERM");
}

export function requireSetup() {
  if (!existsSync(VENV_PY) || !existsSync(VITE)) fail("Not installed yet. Run: npm install");
}
