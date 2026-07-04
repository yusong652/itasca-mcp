# itasca-mcp Agent Bootstrap Guide

Use this guide when an agent needs to set up `itasca-mcp` execution end-to-end on a Windows machine. It works for any ITASCA engine — PFC, FLAC, 3DEC, MPoint, MassFlow — since they share the same install layout, embedded Python, and bridge.

## Target Outcome

1. MCP client is configured to run `itasca-mcp`.
2. `itasca-mcp-bridge` is installed in the correct ITASCA engine embedded Python environment.
3. Bridge is started in the ITASCA engine GUI via `itasca_mcp_bridge.start()`.
4. MCP execution tools are verified with `itasca_execute_code`.

## Agent Execution Rules

- Use bounded, fast path detection for `itasca_path`; avoid full-drive recursive scans by default.
- Install the package with the engine's embedded interpreter (`itasca_python`). Resolve it by globbing `{itasca_path}/exe64/python*/python.exe` (each install ships exactly one):
  - PFC 6.0 / 7.0 and FLAC 7.0: `exe64/python36/python.exe`
  - 9.0 (all engines): `exe64/python310/python.exe`
  - If the glob resolves to `python27` (FLAC 6.x), stop: the bridge requires Python >= 3.6 and cannot run in that engine. Report this to the user and recommend upgrading to 7.0+.
- If a step fails, report the exact command and output, then apply the next fallback.
- Respect step ownership labels:
  - `[AGENT]` means the agent should execute the action.
  - `[USER ACTION REQUIRED]` means the user must execute it manually.

## Step 1 - Configure MCP Client

[AGENT]

Use the client-specific Step 1 profile:

- OpenCode: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-opencode.md>
- Claude Code: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-claude.md>
- Codex: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-codex.md>
- Gemini CLI: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-gemini.md>
- GitHub Copilot CLI: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-copilot.md>
- toyoura-nagisa: <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap-toyoura-nagisa.md>

If raw URL fetch is unavailable, use repository-relative paths:

- `docs/agentic/itasca-mcp-bootstrap-opencode.md`
- `docs/agentic/itasca-mcp-bootstrap-claude.md`
- `docs/agentic/itasca-mcp-bootstrap-codex.md`
- `docs/agentic/itasca-mcp-bootstrap-gemini.md`
- `docs/agentic/itasca-mcp-bootstrap-copilot.md`
- `docs/agentic/itasca-mcp-bootstrap-toyoura-nagisa.md`

Apply this MCP launch contract in your client's native config format:

- server id/name: `itasca-mcp`
- primary launch command: `uvx itasca-mcp`
- fallback launch command: `uv tool run itasca-mcp`
- enable server in client config
- prefer user/global-level config by default; fall back to workspace-level config only if the global config is unavailable or write-blocked

> Rationale: `itasca-mcp` bridges a machine-local ITASCA engine GUI over a localhost bridge, so the capability is machine-scoped, not project-scoped. An engine working directory is a simulation workspace and is rarely a shared repo, so workspace-scoped config mainly creates a "switch working directory → tool disappears, must re-run bootstrap" footgun. Keep the config global so it survives directory changes; the per-client profile names the exact user-scope target and the preferred CLI where one exists.

When editing MCP config, use this order:

1. If config file does not exist, create it.
2. If config exists but has no `itasca-mcp` entry, merge/add only that entry.
3. If `itasca-mcp` already exists, validate/update only MCP launch fields (`command`, `args`, and client-specific extras).
4. Do not overwrite unrelated MCP servers.

## Step 2 - Resolve `itasca_path`

[AGENT]

`itasca_path` should be the ITASCA engine install directory containing `exe64/<engine>*_gui.exe` (e.g. `pfc2d*_gui.exe`, `pfc3d*_gui.exe`, `flac3d*_gui.exe`, `3dec*_gui.exe`).

### 2.0 Quick probe (fast path)

Try lightweight checks first:

```bash
ls "C:/Program Files/Itasca"
ls "D:/Program Files/Itasca"
```

If obvious install folders are found, immediately drill into those folders and check `exe64/*_gui.exe` before running the full PowerShell lookup.

### 2.1 Bounded common-path lookup (recommended)

Run in PowerShell (not bash) to avoid `$` variable expansion issues:

```powershell
$roots=@('C:\Program Files\Itasca','D:\Program Files\Itasca','C:\Itasca','D:\Itasca');
$hits=@();
foreach($r in $roots){
  if(Test-Path $r){
    Get-ChildItem -Path $r -Directory -ErrorAction SilentlyContinue | ForEach-Object {
      $exeDir=Join-Path $_.FullName 'exe64';
      if(Test-Path $exeDir){
        Get-ChildItem -Path $exeDir -Filter '*_gui.exe' -File -ErrorAction SilentlyContinue | ForEach-Object {
          $hits += [PSCustomObject]@{ itasca_path=$_.Directory.Parent.FullName; gui_exe=$_.FullName }
        }
      }
    }
  }
}
$hits | Sort-Object gui_exe -Unique | Select-Object -First 10
```

If the agent shell is bash on Windows, wrap the PowerShell script in single quotes:

```bash
powershell -NoProfile -Command '& {$roots=@("C:\Program Files\Itasca","D:\Program Files\Itasca","C:\Itasca","D:\Itasca"); $hits=@(); foreach($r in $roots){ if(Test-Path $r){ Get-ChildItem -Path $r -Directory -ErrorAction SilentlyContinue | ForEach-Object { $exeDir=Join-Path $_.FullName "exe64"; if(Test-Path $exeDir){ Get-ChildItem -Path $exeDir -Filter "*_gui.exe" -File -ErrorAction SilentlyContinue | ForEach-Object { $hits += [PSCustomObject]@{ itasca_path=$_.Directory.Parent.FullName; gui_exe=$_.FullName } } } } } }; $hits | Sort-Object gui_exe -Unique | Select-Object -First 10 }'
```

If multiple engine GUIs are found (e.g. both PFC and FLAC, or both 2D and 3D variants) and the user did not specify which to use, ask the user which engine to target before proceeding.

### 2.2 Optional registry lookup (fallback)

Some installations are not registered in Windows uninstall keys; treat this as optional.

```powershell
$keys=@('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*');
$hits=@();
foreach($k in $keys){
  Get-ItemProperty $k -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -match 'PFC|FLAC|3DEC|MassFlow|MPoint|Itasca' } |
    ForEach-Object {
      if($_.InstallLocation){
        $exeDir=Join-Path $_.InstallLocation 'exe64';
        Get-ChildItem -Path $exeDir -Filter '*_gui.exe' -File -ErrorAction SilentlyContinue | ForEach-Object {
          $exe=$_.FullName;
          $hits += [PSCustomObject]@{ itasca_path=$_.Directory.Parent.FullName; gui_exe=$exe }
        }
      }
    }
}
$hits | Sort-Object gui_exe -Unique | Select-Object -First 10
```

If still unresolved, ask user to provide exact `itasca_path`.

## Step 3 - Install/Upgrade Bridge in the Engine's Python

[AGENT]

First resolve `itasca_python`, the engine's embedded interpreter. Detect it directly (one `python*` folder per install):

```powershell
Get-ChildItem -Path "{itasca_path}/exe64/python*/python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
```

Known mapping if you prefer to resolve it by version: PFC 6.0/7.0 and FLAC 7.0 → `exe64/python36/python.exe`, 9.0 → `exe64/python310/python.exe`. FLAC 6.x ships `exe64/python27` — Python 2.7 cannot run the bridge; do not attempt the install there.

Check current package:

```powershell
& "{itasca_python}" -m pip show itasca-mcp-bridge
```

Install/upgrade:

```powershell
& "{itasca_python}" -m pip install --user --upgrade itasca-mcp-bridge
```

If that index is unreachable (PyPI blocked behind a regional network or
corporate proxy), retry via the Tsinghua mirror -- the same fallback the
bridge's own self-upgrade performs automatically:

```powershell
& "{itasca_python}" -m pip install --user --upgrade --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn itasca-mcp-bridge
```

Verify import and version:

```powershell
& "{itasca_python}" -c "import itasca_mcp_bridge; print(itasca_mcp_bridge.__version__)"
```

Ignore pip upgrade warnings in this environment. Older embedded interpreters commonly use older pip builds.

## Step 4 - Start the Engine GUI

[AGENT]

If the engine GUI is not open yet, start it from terminal (do not rely on command exit code to infer startup success):

```bash
powershell -NoProfile -Command "$gui=Get-ChildItem '{itasca_path}/exe64' -Filter '*_gui.exe' -File -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName; if(-not $gui){ throw 'No *_gui.exe found under exe64' }; Start-Process $gui"
```

Confirm the engine process is running:

```bash
powershell -NoProfile -Command "$procs=Get-CimInstance Win32_Process | Where-Object { $_.Name -match '_gui\\.exe$' }; if($procs){$procs | Select-Object Name,ProcessId | Format-Table -AutoSize} else {Write-Output 'No ITASCA engine GUI process found'}"
```

If several engine GUIs are available and the user did not specify, ask which to start. For PFC specifically, if both `pfc2d*_gui.exe` and `pfc3d*_gui.exe` exist, prefer 3D (`pfc3d`) by default.

[USER ACTION REQUIRED]

Ask the user to run this in the engine GUI's IPython console (the package was
already installed in Step 3), then restart the client session before Step 5:

```python
import itasca_mcp_bridge
itasca_mcp_bridge.start()
```

On every start the bridge checks PyPI for a newer release and self-upgrades
before starting, so this same two-liner keeps the install current in later
sessions. The check is best-effort: offline machines just start the
installed version.

Expected output includes:

- `Itasca MCP Bridge Server`
- `http://localhost:9001`
- `Task loop running via Qt timer`

## Step 5 - Verify from MCP Client

[AGENT]

Then reconnect MCP client and call:

- `itasca_execute_code` with a simple snippet, e.g. `print('hello from ITASCA')`

If `itasca_*` MCP tools are not visible in the client, ask user to fully restart client session first, then retry.

Success example (shape may vary by client):

```json
{
  "ok": true,
  "data": {
    "stdout": "hello from ITASCA\n",
    "result": null
  }
}
```

`ok: true` means the full MCP → bridge → engine pipeline is working.

## Troubleshooting

- `Connection refused`:
  - Bridge not running in the engine GUI, or port `9001` not available.
- `No module named itasca_mcp_bridge`:
  - Bridge package not installed in the engine's embedded Python (or installed into the
    wrong interpreter). Re-run Step 3 against the resolved `itasca_python`.
  - One-shot fallback: paste the contents of
    <https://raw.githubusercontent.com/yusong652/itasca-mcp/main/addon.py> into the
    engine's IPython console -- it installs (with mirror fallback) and starts the
    bridge in one go.
- `status remains pending / plot diagnostic timeout during solve`:
  - Upgrade to the latest `itasca-mcp-bridge` release.
- `pip` upgrade warning after install:
  - Usually safe to ignore if package install completed successfully.
- Need to confirm GUI process from terminal:
  - Run the exact GUI filter command from Step 4 (matches `*_gui.exe`).
- `itasca_*` tools missing in client after setup:
  - Client session was not fully restarted after Step 1. Close/reopen client session and retry Step 5.
- PowerShell error `Unexpected token '-m'`:
  - Quoted executable path was not invoked with `&`. Use `& "{itasca_python}" -m ...`.
