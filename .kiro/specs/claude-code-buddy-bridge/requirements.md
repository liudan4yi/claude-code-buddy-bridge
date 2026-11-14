# Requirements Document

## Introduction
This document captures the requirements for claude-code-buddy-bridge, a small daemon that lets the claude-desktop-buddy ESP32 device guard Claude Code CLI sessions. The device was built for Claude Desktop; Claude Code does not speak BLE, so the bridge translates between Claude Code HTTP hooks and the device's BLE Nordic-UART JSON protocol.

## Requirements

### Requirement 1: Permission approval on the device
**User Story:** As a Claude Code user, I want guarded tool calls to appear on my buddy device so that I can approve or deny them with a physical button.

#### Acceptance Criteria
1. WHEN Claude Code is about to run a guarded tool (Bash, Write, Edit, ...), THE bridge SHALL show the prompt on the device and block the tool call until a button is pressed.
2. WHEN the user single-clicks the device button, THE bridge SHALL return `allow` to Claude Code.
3. WHEN the user long-presses the device button, THE bridge SHALL return `deny` to Claude Code.
4. WHEN the user double-clicks the device button, THE bridge SHALL treat it as a local pet-species switch with no effect on Claude Code.

### Requirement 2: Fail-safe behavior
**User Story:** As a Claude Code user, I want the bridge to never silently allow a guarded tool when something is wrong, so that a dropped device cannot approve something I did not see.

#### Acceptance Criteria
1. WHEN the device is offline or not connected, THE bridge SHALL return `ask` so Claude Code falls back to its normal permission dialog.
2. WHEN no button is pressed within ~110 s, THE bridge SHALL return `ask`.
3. WHEN the tool is not in the guarded list, THE bridge SHALL return `allow` without sending anything to the device.

### Requirement 3: Multi-session tracking
**User Story:** As a Claude Code user running several sessions at once, I want the device's session counts and info page to stay in sync so that I can see what is running.

#### Acceptance Criteria
1. WHEN a Claude Code session starts, THE bridge SHALL register it via the SessionStart hook and update the device's session count.
2. WHEN a session ends or stops, THE bridge SHALL deregister it via the SessionEnd/Stop hooks.
3. WHEN several sessions run concurrently, THE bridge SHALL track each session id independently.

### Requirement 4: Unchanged device firmware
**User Story:** As a buddy device owner, I want to use the bridge without reflashing my device, so that the same pet keeps working with Claude Desktop.

#### Acceptance Criteria
1. THE bridge SHALL emit exactly the same newline-delimited JSON the device already parses.
2. THE bridge SHALL read back the same `{"cmd":"permission","decision":...}` button replies.
3. THE bridge SHALL NOT require any change to the device firmware.

### Requirement 5: BLE pairing
**User Story:** As a user setting up the bridge, I want pairing to work once through the operating system so that the bridge can talk to the encrypted device.

#### Acceptance Criteria
1. THE bridge SHALL connect to a device advertising as `Claude-XXXX` after the OS has completed pairing once (LE Secure Connections, passkey).
2. ON macOS, THE bridge SHALL rely on the system Bluetooth pairing flow because pairing via Bleak is limited.
3. ON Linux, THE bridge SHALL work after pairing once with `bluetoothctl`.
