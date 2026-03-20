# Architecture Notes

## Chosen Stack

- Language: Python 3.11+
- Desktop UI: PySide6
- Windows integration: native Win32 through `ctypes`
- Hotkeys: native `RegisterHotKey` with a dedicated listener thread
- Persistence: versioned `config.json` saved next to the runtime entrypoint during the MVP stage

## Package Layout

```text
src/autoclicker/
  app.py                # QApplication bootstrap and runtime-path helpers
  __main__.py           # python -m autoclicker entrypoint
  domain/models.py      # Shared dataclasses and serialization helpers
  services/
    click_engine.py     # Background clicking worker and runtime state
    config_store.py     # Versioned config.json load/save
    hotkey_service.py   # Native global hotkey registration
    window_service.py   # Window enumeration and HWND targeting
  ui/
    hotkey_edit.py      # Hotkey capture widget
    main_window.py      # Main desktop shell and feature panels
    theme.py            # Application styling
scripts/
  verify.ps1            # Syntax + unit-test verification
  build.ps1             # PyInstaller packaging helper
```

## Delivery Sequence

1. Step 1: Scaffold the package, app shell, and service boundaries.
2. Step 2: Implement Win32 window discovery and target selection.
3. Step 3: Prove background click delivery against Notepad, then browser targets.
4. Step 4: Capture and convert screen coordinates into target-relative client points.
5. Step 5: Build the click loop with delay/random-delay/count constraints.
6. Step 6: Register configurable global hotkeys and connect them to the engine.
7. Step 7: Bind real service logic into the UI.
8. Step 8: Persist and normalize settings through a versioned config file.
9. Step 9: Add verification, packaging support, and runtime polish for Windows delivery.

## Immediate Decisions

- Keep the app single-process with a responsive UI thread and background worker threads.
- Store user settings in `config.json` for transparency and easy debugging during the MVP stage.
- Keep Win32-specific logic inside small service classes so later platform-specific changes stay isolated from the UI.
- Prefer build and verification scripts that work from the repo root and can be reused after packaging.
