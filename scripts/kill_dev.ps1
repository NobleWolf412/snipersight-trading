# Thoroughly terminate the SniperSight dev stack on Windows.
# WHY this exists: `kill-port` only frees the port, but the uvicorn `--reload` WATCHER parent
# respawns the server child and re-grabs the port, so kill-port never sticks. And Ctrl+C in the
# VS Code terminal orphans the python tree on Windows (it kills the wrapper, not the children).
# This kills the whole tree by command-line match (taskkill /T = process + its subtree), so the
# watcher can't respawn. kill-port (run after, by the Node caller) is just a backstop for vite.
$ErrorActionPreference = 'SilentlyContinue'

# 1) Backend python tree: the uvicorn `--reload` WATCHER (its cmdline has uvicorn+backend.api_server)
#    AND its multiprocessing-spawn children (server + scan workers — their cmdline is the spawn
#    bootstrap, NO 'uvicorn', so they must be matched another way or they survive and keep the
#    inherited port-8001 socket bound). The backend interpreter is the SYSTEM python (Program Files
#    or the repo venv); Claude/serena tooling python lives in %AppData%\uv — so a non-AppData
#    multiprocessing.spawn python IS a backend child, and an AppData one is tooling (spared).
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -eq 'python.exe' -and (
      ($_.CommandLine -match 'uvicorn.*backend\.api_server') -or
      ($_.CommandLine -match 'multiprocessing.spawn' -and $_.ExecutablePath -notlike '*AppData*')
    )
  } |
  ForEach-Object {
    Write-Host "kill_dev: backend python PID $($_.ProcessId)"
    & taskkill /F /T /PID $_.ProcessId 2>$null | Out-Null
  }

# 2) leftover `concurrently` wrappers for THIS repo (orphaned by Ctrl+C). Matched by the
#    project-specific "dev:frontend" arg so we never touch concurrently in other projects.
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'dev:frontend' } |
  ForEach-Object {
    Write-Host "kill_dev: concurrently wrapper PID $($_.ProcessId)"
    & taskkill /F /T /PID $_.ProcessId 2>$null | Out-Null
  }
