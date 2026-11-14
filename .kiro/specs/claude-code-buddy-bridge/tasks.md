# Implementation Plan

- [x] 1. BLE client (`bridge/ble_client.py`)
  - [x] Scan for a device advertising as `Claude-XXXX`
  - [x] Connect over BLE NUS and send newline-delimited JSON
  - [x] Read back `{"cmd":"permission","decision":...}` button replies

- [x] 2. Session state (`bridge/session_state.py`)
  - [x] Track sessions by Claude Code session id
  - [x] Build heartbeat JSON for the device's session counts and info page

- [x] 3. Daemon and hooks (`bridge/daemon.py`, `examples/settings.hooks.json`)
  - [x] HTTP hook server on 127.0.0.1:8765
  - [x] PreToolUse approval flow: guarded tool -> device prompt -> allow/deny
  - [x] SessionStart / SessionEnd / Stop hooks keep the device in sync
  - [x] Fail-safe: device offline or ~110 s timeout returns `ask`

- [x] 4. Documentation and setup
  - [x] README: install, run, wire up Claude Code, button mapping, fail-safe, BLE pairing note
  - [x] `requirements.txt` (Python 3.10+, Bleak)

- [ ] 5. Next steps
  - [ ] Support Kiro and other CLI agents through the same bridge (hook protocol is generic)
  - [ ] Add a small web dashboard for the bridge's session state
  - [ ] Package the daemon as a single installable
  - [ ] Add a "deny with reason" path so a long-press can send a short note back to the agent
