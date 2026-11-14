# claude-code-buddy-bridge

The ESP32 buddy device was built for Claude Desktop, which speaks a BLE
Nordic-UART JSON protocol directly. Claude Code is a CLI and does not speak BLE
— so this bridge sits in between:

```
Claude Code (N sessions) --HTTP hooks--> bridge daemon --BLE NUS--> ESP32 buddy
                                          (127.0.0.1:8765)          (unchanged firmware)
```

- **Permission approval**: when Claude Code is about to run a guarded tool
  (Bash/Write/Edit/…), the bridge shows the prompt on the device and **blocks
  until you press the button** — single-click approves, long-press denies.
- **Live session status**: SessionStart/End/Stop hooks keep the device's
  session counts and info page in sync across multiple concurrent sessions.

The device firmware is **not modified**: the bridge emits exactly the same
newline-delimited JSON (`{"running":N,...,"prompt":{...}}`) that the device
already parses, and reads back the same `{"cmd":"permission","decision":...}`
button replies.

## Requirements

- macOS or Linux with a BLE adapter
- Python 3.10+
- A flashed, **already-paired** buddy device (see pairing note below)

## Install

```bash
cd claude-code-buddy-bridge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m bridge.daemon -v      # -v for debug logging
```

The daemon scans for a device advertising as `Claude-XXXX`, connects, and
starts the HTTP server on `127.0.0.1:8765`.

## Wire up Claude Code

Merge `examples/settings.hooks.json` into your Claude Code settings
(`~/.claude/settings.json` for all projects, or `.claude/settings.json` per
project). Then start a Claude Code session — guarded tool calls will appear on
the device.

## How approval maps to buttons

| Device action | Result |
|---|---|
| Single click | **Approve** the pending tool call |
| Long press | **Deny** the pending tool call |
| Double click | Switch pet species (local, no effect on Claude Code) |

## Fail-safe behavior

The bridge **never silently allows** a guarded tool when something is wrong:

| Situation | Decision returned to Claude Code |
|---|---|
| Device offline / not connected | `ask` (falls back to the normal CLI permission dialog) |
| No button press within ~110 s | `ask` |
| Non-guarded tool | `allow` (not sent to device) |
| Button: single-click | `allow` |
| Button: long-press | `deny` |

## BLE pairing note (important)

The device's GATT characteristics are **encrypted** (LE Secure Connections with
a passkey). Before the bridge can talk to it, the OS must have completed pairing
once:

- **macOS**: pairing via `bleak` is limited. Pair the device once through the
  system flow (it will show a passkey on screen), then run the bridge — the OS
  reuses the bond. If the bridge can't read/write encrypted characteristics,
  re-pair from **System Settings → Bluetooth**.
- **Linux (BlueZ)**: pair once with `bluetoothctl` (`pair <addr>`, enter the
  passkey shown on the device), then run the bridge.

## Configuration

```
python -m bridge.daemon \
  --host 127.0.0.1 \
  --port 8765 \
  --guard Bash,Write,Edit,MultiEdit,NotebookEdit \
  -v
```

`--guard` is the comma-separated list of tool names that require physical
approval. Everything else is auto-allowed.

## Layout

```
bridge/
  ble_client.py     # BLE NUS connection to the device
  session_state.py  # multi-session tracking -> heartbeat JSON
  daemon.py         # HTTP hook server + approval coordination
examples/
  settings.hooks.json  # Claude Code hooks config to copy in
```

## Status

Early. The hooks side is straightforward; the BLE-on-macOS pairing path is the
part most likely to need hands-on tweaking for your setup.
