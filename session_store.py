"""Persist session IDs to disk so they survive MCP server restarts."""

import json
import time
from pathlib import Path

_STORE_PATH = Path.home() / ".cursor" / "mcp_sessions.json"


def _load() -> dict:
    if _STORE_PATH.exists():
        try:
            return json.loads(_STORE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(data: dict) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2))


def save_session(session_id: str, label: str = "", workspace: str = "") -> None:
    data = _load()
    data[session_id] = {
        "label": label,
        "workspace": workspace,
        "created_at": int(time.time()),
        "last_used": int(time.time()),
    }
    _save(data)


def touch_session(session_id: str) -> None:
    data = _load()
    if session_id in data:
        data[session_id]["last_used"] = int(time.time())
        _save(data)


def list_sessions() -> list[dict]:
    data = _load()
    sessions = []
    for sid, meta in data.items():
        sessions.append({"session_id": sid, **meta})
    return sorted(sessions, key=lambda s: s.get("last_used", 0), reverse=True)


def delete_session(session_id: str) -> bool:
    data = _load()
    if session_id in data:
        del data[session_id]
        _save(data)
        return True
    return False
