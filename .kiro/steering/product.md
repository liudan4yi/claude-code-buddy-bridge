# Product Overview

## What it is
claude-code-buddy-bridge connects the claude-desktop-buddy ESP32 hardware device to Claude Code CLI. The buddy was built for Claude Desktop, which speaks a BLE Nordic-UART JSON protocol directly. Claude Code is a CLI and does not speak BLE, so this bridge sits between them.

## Who it is for
Anyone who built (or bought) a claude-desktop-buddy ESP32 device and now lives in Claude Code CLI all day, and wants the same physical approval flow — a real button press — for guarded tool calls.

## Key features
- **Permission approval**: when Claude Code is about to run a guarded tool (Bash, Write, Edit, ...), the bridge shows the prompt on the device and blocks until you press a button. Single-click approves, long-press denies.
- **Live session status**: SessionStart/End/Stop hooks keep the device's session counts and info page in sync across multiple concurrent sessions.
- **Unchanged firmware**: the bridge emits exactly the same newline-delimited JSON the device already parses, and reads back the same button replies. No device firmware change is needed.
- **Fail-safe**: the bridge never silently allows a guarded tool when something is wrong. Device offline or no button press within ~110 s returns `ask`, so Claude Code falls back to its normal permission dialog.
