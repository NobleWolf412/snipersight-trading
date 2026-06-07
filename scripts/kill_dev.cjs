#!/usr/bin/env node
/*
 * Cross-platform dev-stack killer for `npm run kill`.  (.cjs: package.json is "type":"module",
 * so this CommonJS script — which uses require/__dirname — must be .cjs.)
 *
 * The old `kill-port 5000 8001` was insufficient: the uvicorn `--reload` WATCHER parent respawns
 * the port-bound server child, so kill-port frees the port and the watcher immediately refills it.
 * (And Ctrl+C on Windows orphans the python tree rather than killing it.) This kills the uvicorn
 * TREE by command-line match first (so nothing respawns), then frees the ports as a backstop.
 */
const { execSync } = require("child_process");
const path = require("path");

const run = (cmd) => {
  try {
    execSync(cmd, { stdio: "inherit" });
  } catch {
    /* non-fatal: nothing to kill / already gone */
  }
};

if (process.platform === "win32") {
  // PowerShell does the cmdline-match + taskkill /T tree-kill (clean, no quoting hell here).
  run(`powershell -NoProfile -ExecutionPolicy Bypass -File "${path.join(__dirname, "kill_dev.ps1")}"`);
} else {
  // -9 -f matches the full command line; kills the reload watcher + its children.
  run(`pkill -9 -f "uvicorn.*backend.api_server" || true`);
  run(`pkill -9 -f "concurrently.*dev:frontend" || true`);
}

// Backstop: free the ports (catches vite on 5000 + any straggler still bound to 8001).
run("npx --yes kill-port 5000 8001");
console.log("kill_dev: ports 5000/8001 freed + uvicorn reload-watcher tree terminated.");
