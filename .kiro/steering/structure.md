# Project Structure

## Layout
```
bridge/
  ble_client.py     # BLE NUS connection to the device
  session_state.py  # multi-session tracking -> heartbeat JSON
  daemon.py         # HTTP hook server + approval coordination
examples/
  settings.hooks.json  # Claude Code hooks config to copy in
```

## Conventions
- The daemon is the only entry point: `python -m bridge.daemon [-v]`
- The bridge speaks the device's existing newline-delimited JSON protocol; it does not define a new device protocol
- Guarded tools are configured via `--guard` (default: Bash, Write, Edit, MultiEdit, NotebookEdit)
- Session state is tracked per Claude Code session id so several sessions can run concurrently
