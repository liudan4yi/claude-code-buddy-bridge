"""Session + prompt state tracking for concurrent Claude Code sessions.

A single bridge daemon receives hook events from every Claude Code process via
HTTP. This module aggregates them into the heartbeat shape the ESP32 firmware
expects:

    {"total":N,"running":R,"waiting":W,"completed":bool,"entries":[...],
     "prompt":{"id","tool","hint"}}

Protocol fields are derived from claude-desktop-buddy-esp32's protocol_handler.cc.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    session_id: str
    title: str = ""
    cwd: str = ""
    state: str = "running"  # running | waiting | idle
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


@dataclass
class PendingPrompt:
    prompt_id: str
    session_id: str
    tool: str
    hint: str
    created_at: float = field(default_factory=time.time)


class SessionTracker:
    """Thread/async-safe-enough state map. Mutated only from the asyncio loop."""

    def __init__(self):
        self.sessions: dict[str, Session] = {}
        # Only one prompt is shown on the device at a time (single-button UX).
        self.active_prompt: Optional[PendingPrompt] = None

    # --- session lifecycle ---
    def session_start(self, session_id: str, title: str = "", cwd: str = "") -> None:
        s = self.sessions.get(session_id)
        if s is None:
            self.sessions[session_id] = Session(session_id, title=title, cwd=cwd)
        else:
            s.last_activity = time.time()
            s.state = "running"

    def session_end(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        if self.active_prompt and self.active_prompt.session_id == session_id:
            self.active_prompt = None

    def mark_idle(self, session_id: str) -> None:
        s = self.sessions.get(session_id)
        if s:
            s.state = "idle"
            s.last_activity = time.time()

    def mark_running(self, session_id: str) -> None:
        s = self.sessions.get(session_id)
        if s is None:
            self.sessions[session_id] = Session(session_id)
        else:
            s.state = "running"
            s.last_activity = time.time()

    # --- permission prompts ---
    def set_prompt(self, prompt_id: str, session_id: str, tool: str, hint: str) -> None:
        self.active_prompt = PendingPrompt(prompt_id, session_id, tool, hint)
        s = self.sessions.get(session_id)
        if s:
            s.state = "waiting"

    def clear_prompt(self, prompt_id: Optional[str] = None) -> None:
        if self.active_prompt is None:
            return
        if prompt_id is None or self.active_prompt.prompt_id == prompt_id:
            sid = self.active_prompt.session_id
            self.active_prompt = None
            s = self.sessions.get(sid)
            if s and s.state == "waiting":
                s.state = "running"

    # --- heartbeat rendering ---
    def heartbeat(self) -> dict:
        total = len(self.sessions)
        running = sum(1 for s in self.sessions.values() if s.state == "running")
        waiting = sum(1 for s in self.sessions.values() if s.state == "waiting")

        # Up to 8 short status lines for the device info page.
        entries = []
        for s in sorted(self.sessions.values(), key=lambda x: x.started_at):
            label = s.title or (s.cwd.rsplit("/", 1)[-1] if s.cwd else s.session_id[:8])
            entries.append(f"{label}: {s.state}"[:91])
            if len(entries) >= 8:
                break

        hb: dict = {
            "total": total,
            "running": running,
            "waiting": waiting,
            "completed": total == 0,
            "entries": entries,
        }
        if self.active_prompt:
            hb["prompt"] = {
                "id": self.active_prompt.prompt_id,
                "tool": self.active_prompt.tool[:19],
                "hint": self.active_prompt.hint[:43],
            }
        return hb
