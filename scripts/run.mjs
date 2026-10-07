// One-shot tasks: build | serve | test | fjg <args>
import { BACKEND, FRONTEND, TSC, VENV_PY, VITE, fail, log, requireSetup, run } from "./lib.mjs";
import { ensurePortsFree } from "./ports.mjs";

requireSetup();
const [task, ...rest] = process.argv.slice(2);

switch (task) {
  case "build":
    run(process.execPath, [TSC, "-b"], { cwd: FRONTEND });
    run(process.execPath, [VITE, "build"], { cwd: FRONTEND });
    break;
  case "serve": // production-like: built UI served by FastAPI on one port
    run(process.execPath, [TSC, "-b"], { cwd: FRONTEND });
    run(process.execPath, [VITE, "build"], { cwd: FRONTEND });
    await ensurePortsFree([8000]);
    log("Serving on http://127.0.0.1:8000");
    run(VENV_PY, ["-m", "uvicorn", "app.main:app", "--port", "8000"], { cwd: BACKEND });
    break;
  case "test":
    run(VENV_PY, ["-m", "pytest", "-q", ...rest], { cwd: BACKEND });
    run(process.execPath, [TSC, "-b"], { cwd: FRONTEND });
    break;
  case "fjg":
    run(VENV_PY, ["-m", "scraper.cli", ...rest], { cwd: BACKEND });
    break;
  default:
    fail(`Unknown task: ${task}`);
}
