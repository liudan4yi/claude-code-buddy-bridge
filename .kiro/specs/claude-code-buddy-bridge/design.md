# Design Document

## Overview
A Python daemon sits between Claude Code CLI and the ESP32 buddy device. Claude Code sends HTTP hooks to the daemon on 127.0.0.1:8765; the daemon forwards them to the device over BLE Nordic UART (NUS) and returns the device's decision to Claude Code.

## Architecture
```
Claude Code (N sessions) --HTTP hooks--> bridge daemon --BLE NUS--> ESP32 buddy
                                           (127.0.0.1:8765)          (unchanged firmware)
```

## Components
- `bridge/daemon.py` — HTTP hook server and approval coordination. Receives PreToolUse / SessionStart / SessionEnd / Stop hooks, asks the device for guarded tools, and returns `allow` / `deny` / `ask`.
- `bridge/ble_client.py` — BLE NUS connection to the device. Scans for `Claude-XXXX`, connects, sends newline-delimited JSON, and reads button replies.
- `bridge/session_state.py` — Multi-session tracking. Keeps a per-session registry and builds the heartbeat JSON that keeps the device's session counts and info page in sync.
- `examples/settings.hooks.json` — Claude Code hooks configuration to merge into `~/.claude/settings.json` (or per-project `.claude/settings.json`).

## Data flow
1. Claude Code triggers a hook (for example PreToolUse for Bash) and POSTs to the daemon.
2. The daemon checks whether the tool is in the guarded list (`--guard`).
3. If guarded, the daemon sends the prompt JSON to the device over BLE and waits for a button reply (timeout ~110 s).
4. The device shows the prompt; single-click returns `allow`, long-press returns `deny`.
5. The daemon returns the decision to Claude Code. On any error or timeout it returns `ask`.

## Fail-safe and error handling
- Device offline / not connected: return `ask`.
- No button press within ~110 s: return `ask`.
- Non-guarded tool: return `allow` without touching the device.
- The bridge never returns `allow` for a guarded tool unless the device explicitly approved it.

## Configuration
- `--host` (default 127.0.0.1), `--port` (default 8765), `--guard` (comma-separated tool names), `-v` for debug logging.
