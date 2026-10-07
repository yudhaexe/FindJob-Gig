// `npm install` / `npm run setup`: backend venv + Python deps, then frontend deps.
import { existsSync } from "node:fs";
import { BACKEND, FRONTEND, VENV_PY, c, fail, findPython, log, npm, run } from "./lib.mjs";

log("Backend: Python virtualenv");
if (existsSync(VENV_PY)) {
  console.log(c.dim("  backend/.venv already exists"));
} else {
  const py = findPython();
  if (!py) fail("Python 3.11+ not found. Install it from https://www.python.org/downloads/ and retry.");
  console.log(c.dim(`  using Python ${py.version} (${py.cmd} ${py.pre.join(" ")})`));
  run(py.cmd, [...py.pre, "-m", "venv", ".venv"], { cwd: BACKEND });
}

log("Backend: installing Python packages");
run(VENV_PY, ["-m", "pip", "install", "-q", "--upgrade", "pip"], { cwd: BACKEND });
run(VENV_PY, ["-m", "pip", "install", "-q", "-e", ".[dev]"], { cwd: BACKEND });

log("Frontend: installing npm packages");
npm(["install", "--no-fund", "--no-audit"], FRONTEND);

log(`Done. Start everything with ${c.cyan("npm start")}`);
