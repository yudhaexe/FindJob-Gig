// Make sure the dev ports belong to *this* launch. A leftover `npm start` (window closed without
// Ctrl+C, or a second start.bat) keeps serving old code: on Windows a second uvicorn can bind the
// same port and the old one still answers, and Vite silently moves to the next port.
import { spawnSync } from "node:child_process";
import { connect } from "node:net";
import { IS_WIN, ROOT, c, fail, log } from "./lib.mjs";

/** Is something accepting connections on localhost:port (IPv4 or IPv6)? */
function busy(port) {
  const tryHost = (host) =>
    new Promise((resolve) => {
      const s = connect({ host, port });
      const done = (v) => {
        s.destroy();
        resolve(v);
      };
      s.setTimeout(500, () => done(false));
      s.once("connect", () => done(true));
      s.once("error", () => done(false));
    });
  return Promise.all([tryHost("127.0.0.1"), tryHost("::1")]).then((r) => r.some(Boolean));
}

// For each listener on the ports, walk up its parents and kill the old `node scripts/dev.mjs` (or, for
// `npm run serve`, the top-most process started from this repo) so the whole old tree goes at once.
// Only chains that contain a process started from this repo folder are touched.
const PS_KILL_OWN = `
$root = $env:FJG_ROOT.ToLower()
$self = [int]$env:FJG_SELF
$ports = $env:FJG_PORTS -split ',' | % { [int]$_ }
$procs = @{}; Get-CimInstance Win32_Process | % { $procs[[int]$_.ProcessId] = $_ }
$foreign = @(); $killed = @{}
foreach ($conn in Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue) {
  $chain = @(); $id = [int]$conn.OwningProcess
  while ($id -and $procs.ContainsKey($id) -and $id -ne $self -and $chain.Count -lt 10) {
    $chain += $procs[$id]; $id = [int]$procs[$id].ParentProcessId
  }
  $ours = $chain | ? { $_.CommandLine -and $_.CommandLine.ToLower().Contains($root) }
  if (-not $ours) { $foreign += "$($conn.LocalPort):$($conn.OwningProcess)"; continue }
  $launcher = $chain | ? { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'scripts[\\\\/]dev\\.mjs' } | Select-Object -Last 1
  $top = if ($launcher) { $launcher } else { @($ours)[-1] }
  if (-not $killed.ContainsKey([int]$top.ProcessId)) {
    taskkill /PID $top.ProcessId /T /F | Out-Null
    $killed[[int]$top.ProcessId] = 1
    "killed $($top.ProcessId)"
  }
}
foreach ($f in $foreign) { "foreign $f" }
`;

export async function ensurePortsFree(ports) {
  const taken = [];
  for (const p of ports) if (await busy(p)) taken.push(p);
  if (!taken.length) return;

  if (IS_WIN) {
    log(`Port ${taken.join(", ")} still used by an earlier run — stopping it…`);
    const r = spawnSync("powershell", ["-NoProfile", "-NonInteractive", "-Command", PS_KILL_OWN], {
      encoding: "utf8",
      env: { ...process.env, FJG_ROOT: ROOT, FJG_SELF: String(process.pid), FJG_PORTS: taken.join(",") },
    });
    const foreign = (r.stdout || "").split(/\r?\n/).filter((l) => l.startsWith("foreign "));
    if (foreign.length) {
      const list = foreign.map((l) => l.slice(8).replace(":", " (pid ") + ")").join(", ");
      fail(`Port in use by another program: ${list}. Close it, then start again.`);
    }
    // taskkill returns before the sockets are released.
    for (let i = 0; i < 20; i++) {
      const still = [];
      for (const p of taken) if (await busy(p)) still.push(p);
      if (!still.length) return;
      await new Promise((res) => setTimeout(res, 250));
    }
  }
  fail(`Port ${taken.join(", ")} is already in use. Stop the other ${c.yellow("npm start")} (Ctrl+C) and try again.`);
}
