# Technology Stack

## Language and runtime
- Python 3.10+
- Runs on macOS or Linux with a BLE adapter

## Key libraries
- Bleak — Bluetooth Low Energy client (BLE Nordic UART / NUS)
- Python standard library HTTP server — receives Claude Code hook events on 127.0.0.1:8765

## Hardware
- ESP32-S3 buddy device running the open-source claude-desktop-buddy firmware (unchanged)
- BLE Nordic UART (NUS) with encrypted GATT characteristics (LE Secure Connections, passkey pairing)

## Integration points
- Claude Code hooks (`examples/settings.hooks.json`): PreToolUse, SessionStart, SessionEnd, Stop
- The daemon scans for a device advertising as `Claude-XXXX`, connects over BLE, and serves HTTP hooks locally

## Configuration
- `--host`, `--port` (default 127.0.0.1:8765), `--guard` (comma-separated guarded tool names), `-v` for debug logging
