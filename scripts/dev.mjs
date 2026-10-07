// `npm start`: backend (FastAPI :8000, auto-reload) + frontend (Vite :5173) in one terminal.
import { BACKEND, FRONTEND, VENV_PY, VITE, c, killTree, requireSetup, startProc } from "./lib.mjs";

requireSetup();

const procs = [
  startProc("api", c.magenta, VENV_PY, ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], BACKEND),
  startProc("web", c.cyan, process.execPath, [VITE, "--port", "5173"], FRONTEND),
];

console.log(`\n  ${c.green("App")}  http://localhost:5173`);
console.log(`  ${c.green("API")}  http://127.0.0.1:8000/docs`);
console.log(c.dim("  Ctrl+C to stop both\n"));

let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  procs.forEach(killTree);
  process.exit(code);
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
for (const p of procs) {
  p.on("exit", (code) => {
    if (!stopping) {
      console.error(c.red(`\nA process exited (code ${code}); stopping the other.`));
      stop(code ?? 1);
    }
  });
}
