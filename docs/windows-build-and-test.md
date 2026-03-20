# Windows Build And Test Guide

## Prerequisites

- Windows 10 or Windows 11
- Python 3.11+
- A desktop session where the target windows are actually visible
- Matching privilege level between the auto-clicker and the target app when possible

## Install

Recommended, because this workspace blocks `pip` from using the default temp folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-deps.ps1
```

Build-only dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-deps.ps1 -BuildOnly
```

Manual equivalent if you prefer to run `pip` yourself:

```powershell
New-Item -ItemType Directory -Force .pip-temp | Out-Null
$env:TMP = (Resolve-Path .pip-temp)
$env:TEMP = $env:TMP
python -m pip install ".[build]"
```

## Run Locally

```powershell
$env:PYTHONPATH = 'src'
python -m autoclicker
```

The app saves `config.json` next to the runtime entrypoint. When the app is packaged, that means the config file sits next to the generated `.exe`.

## Verify Before Shipping

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

This runs:

- `python -m compileall src`
- `python -m unittest discover -s tests -p "test_*.py" -v`

## Build A Windows Executable

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Optional single-file build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -OneFile
```

The default output path is `dist/AdvancedBackgroundAutoClicker`.

## Manual Test Checklist

1. Launch the app and confirm the log mentions whether it loaded an existing config or default settings.
2. Open Notepad, refresh the target list, and select the Notepad window.
3. Capture a point inside Notepad and confirm the point label changes.
4. Use `Test Background Click` with `SendMessage`, then repeat with `PostMessage`.
5. Start a short loop with a low `max_clicks` and verify the counter stops exactly at the limit.
6. Rebind hotkeys, apply them, and verify Start/Stop plus Capture work while the app is unfocused.
7. Close and reopen the app, then confirm target metadata, hotkeys, delivery mode, button, and point settings are restored from `config.json`.
8. Repeat the click test with your real browser or emulator target and note whether it accepts `SendMessage`, `PostMessage`, both, or neither.

## Known Runtime Limits

- Browser tabs and game render surfaces often require targeting a child `HWND`; the app resolves common Chrome-style render children, but some targets will still ignore message-based input.
- Minimized windows may not process click messages even if they accept background clicks while visible.
- Anti-cheat systems, elevated windows, or apps using raw input can block or ignore this technique.
- The desktop shell session used for testing must be interactive; background service sessions are not enough.

## Logs And Crash Reports

- The app writes a rolling diagnostic file to `logs/latest.log`. This is the first file to send back for debugging.
- Each launch also creates a timestamped session log in `logs/session-YYYYMMDD-HHMMSS.log`.
- Unhandled startup or UI exceptions are written to `logs/crash-YYYYMMDD-HHMMSS.log` next to the runtime entrypoint whenever possible.
