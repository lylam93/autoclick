# Architecture Notes

## Chosen Stack

- Language: Python 3.11+
- Desktop UI: PySide6
- Windows integration: `ctypes` + `pywin32`
- Hotkeys: `keyboard` for the MVP, with room to replace it with native Win32 registration later

## Package Layout

```text
src/autoclicker/
  app.py                # QApplication bootstrap
  __main__.py           # python -m autoclicker entrypoint
  domain/models.py      # Shared dataclasses and serialization helpers
  services/
    click_engine.py     # Background clicking worker and runtime state
    config_store.py     # config.json load/save
    hotkey_service.py   # Global hotkey integration
    window_service.py   # Window enumeration and HWND targeting
  ui/
    main_window.py      # Main desktop shell and feature panels
    theme.py            # Application styling
```

## Delivery Sequence

1. Step 1: Scaffold the package, app shell, and service boundaries.
2. Step 2: Implement Win32 window discovery and target selection.
3. Step 3: Prove background click delivery against Notepad, then browser targets.
4. Step 4: Capture and convert screen coordinates into target-relative client points.
5. Step 5: Build the click loop with delay/random-delay/count constraints.
6. Step 6: Register configurable global hotkeys and connect them to the engine.
7. Step 7: Bind real service logic into the UI and persistence layer.

## Immediate Decisions

- Keep the app single-process with a responsive UI thread and background worker threads.
- Store user settings in `config.json` during the MVP stage for transparency and easy debugging.
- Design every service behind a small Python class so later Win32-specific logic stays isolated from the UI.

