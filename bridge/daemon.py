"""claude-code-buddy-bridge daemon.

Bridges Claude Code CLI hooks to a claude-desktop-buddy ESP32 device over BLE.

  Claude Code (N sessions) --HTTP hooks--> this daemon --BLE NUS--> ESP32

Endpoints (configure these as HTTP hooks in Claude Code settings.json):
  POST /pre-tool-use   (blocking)  -> shows prompt on device, waits for button,
                                       returns allow/deny
  POST /session-start  (async)     -> increments session count
  POST /session-end    (async)     -> decrements session count
  POST /stop           (async)     -> marks session idle
  POST /notification   (async)     -> optional: surface permission prompts

Run:  python -m bridge.daemon  (from the repo root)
"""

import argparse
import asyncio
import json
import logging
import uuid
from aiohttp import web

from .ble_client import BuddyBleClient
from .session_state import SessionTracker

log = logging.getLogger("daemon")

# Tools that should require physical approval. Others are auto-allowed.
DEFAULT_GUARDED_TOOLS = {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"}

# How long to wait for a button press before defaulting (must be < hook timeout).
PROMPT_TIMEOUT_S = 110


class Bridge:
    def __init__(self, guarded_tools: set[str]):
        self.tracker = SessionTracker()
        self.guarded_tools = guarded_tools
        self.ble = BuddyBleClient(on_message=self._on_device_message)
        # prompt_id -> Future[bool] resolved when the device replies
        self._pending: dict[str, asyncio.Future] = {}
        self._hb_dirty = asyncio.Event()

    # --- device -> bridge ---
    async def _on_device_message(self, msg: dict) -> None:
        # Button decision: {"cmd":"permission","id":"x","decision":"once"|"deny"}
        # The device firmware sends "once" to approve (single click) and
        # "deny" to reject (long press). "always" is reserved for a future
        # always-allow gesture; treat anything that isn't "deny" as approve.
        if msg.get("cmd") == "permission":
            pid = msg.get("id", "")
            decision = msg.get("decision", "deny")
            approved = decision in ("once", "always", "approve")
            fut = self._pending.get(pid)
            if fut and not fut.done():
                fut.set_result(approved)
            self.tracker.clear_prompt(pid)
            self._hb_dirty.set()

    # --- heartbeat pump: push state to device on change + periodically ---
    async def heartbeat_loop(self):
        while True:
            try:
                await asyncio.wait_for(self._hb_dirty.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            self._hb_dirty.clear()
            if self.ble.connected:
                await self.ble.send_json(self.tracker.heartbeat())

    def _touch(self):
        self._hb_dirty.set()

    # --- HTTP hook handlers ---
    async def handle_pre_tool_use(self, request: web.Request) -> web.Response:
        """Blocking: show the prompt on the device and wait for a button press.

        Always returns HTTP 200 with a PreToolUse decision so a daemon hiccup
        never hard-blocks Claude Code (non-2xx would be treated as non-blocking
        anyway, but an explicit decision is clearer).
        """
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001
            return self._decision("allow", "bridge: bad request body")

        tool = data.get("tool_name", "?")
        session_id = data.get("session_id", "unknown")
        tool_input = data.get("tool_input", {}) or {}

        # Non-guarded tools auto-allow without bothering the device.
        if tool not in self.guarded_tools:
            return self._decision("allow")

        # If no device is connected, fail OPEN to "ask" so the normal CLI
        # dialog still protects the user (don't silently allow).
        if not self.ble.connected:
            return self._decision("ask", "bridge: device offline")

        prompt_id = uuid.uuid4().hex[:12]
        hint = self._hint_for(tool, tool_input)
        self.tracker.set_prompt(prompt_id, session_id, tool, hint)
        self._touch()

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[prompt_id] = fut
        try:
            approved = await asyncio.wait_for(fut, timeout=PROMPT_TIMEOUT_S)
        except asyncio.TimeoutError:
            self.tracker.clear_prompt(prompt_id)
            self._touch()
            return self._decision("ask", "bridge: no response from device")
        finally:
            self._pending.pop(prompt_id, None)

        if approved:
            return self._decision("allow", "approved on device")
        return self._decision("deny", "rejected on device")

    async def handle_session_start(self, request: web.Request) -> web.Response:
        data = await self._safe_json(request)
        sid = data.get("session_id", "unknown")
        title = (data.get("hookSpecificOutput", {}) or {}).get("sessionTitle", "")
        self.tracker.session_start(sid, title=title, cwd=data.get("cwd", ""))
        self._touch()
        return web.json_response({})

    async def handle_session_end(self, request: web.Request) -> web.Response:
        data = await self._safe_json(request)
        self.tracker.session_end(data.get("session_id", "unknown"))
        self._touch()
        return web.json_response({})

    async def handle_stop(self, request: web.Request) -> web.Response:
        data = await self._safe_json(request)
        self.tracker.mark_idle(data.get("session_id", "unknown"))
        self._touch()
        return web.json_response({})

    async def handle_notification(self, request: web.Request) -> web.Response:
        # Fire-and-tell; nothing required, but keep session marked active.
        data = await self._safe_json(request)
        self.tracker.mark_running(data.get("session_id", "unknown"))
        self._touch()
        return web.json_response({})

    # --- helpers ---
    @staticmethod
    async def _safe_json(request: web.Request) -> dict:
        try:
            return await request.json()
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _hint_for(tool: str, tool_input: dict) -> str:
        if tool == "Bash":
            return tool_input.get("command", "")
        if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            return tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
        return json.dumps(tool_input)[:43]

    @staticmethod
    def _decision(decision: str, reason: str = "") -> web.Response:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
            }
        }
        if reason:
            out["hookSpecificOutput"]["permissionDecisionReason"] = reason
        return web.json_response(out)


async def run(host: str, port: int, guarded: set[str]):
    bridge = Bridge(guarded)
    app = web.Application()
    app.add_routes([
        web.post("/pre-tool-use", bridge.handle_pre_tool_use),
        web.post("/session-start", bridge.handle_session_start),
        web.post("/session-end", bridge.handle_session_end),
        web.post("/stop", bridge.handle_stop),
        web.post("/notification", bridge.handle_notification),
    ])

    # Start BLE connection + heartbeat pump in the background.
    asyncio.create_task(bridge.ble.connect())
    asyncio.create_task(bridge.heartbeat_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("Bridge listening on http://%s:%d", host, port)
    # Run forever.
    await asyncio.Event().wait()


def main():
    ap = argparse.ArgumentParser(description="Claude Code <-> buddy BLE bridge")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--guard", default=",".join(sorted(DEFAULT_GUARDED_TOOLS)),
                    help="comma-separated tool names requiring device approval")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    guarded = {t.strip() for t in args.guard.split(",") if t.strip()}
    try:
        asyncio.run(run(args.host, args.port, guarded))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

