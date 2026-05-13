"""Subprocess wrapper around the `agent` CLI with stream-json parsing."""

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_FALLBACK_CANDIDATES = [
    Path.home() / ".local" / "bin" / "agent",
    Path("/usr/local/bin/agent"),
    Path.home() / "bin" / "agent",
    Path("/opt/homebrew/bin/agent"),
    Path("/usr/bin/agent"),
]


def _resolve_agent_binary() -> str:
    raw = os.environ.get("CURSOR_AGENT_PATH")
    if raw is not None and raw.strip():
        resolved = str(Path(raw.strip()).resolve())
        if os.path.isfile(resolved) and os.access(resolved, os.X_OK):
            return resolved
        raise RuntimeError(
            f'CURSOR_AGENT_PATH is set to "{raw}" but that path does not '
            "exist or is not executable.\n\n"
            "Fix: set CURSOR_AGENT_PATH to the correct absolute path to the "
            "`agent` binary, or unset it to let the server find `agent` "
            "automatically.\n\n"
            "Verify your install: run `agent --version` in a terminal where "
            "it works, then `which agent` to find its location."
        )

    which_result = shutil.which("agent")
    if which_result:
        return str(Path(which_result).resolve())

    for candidate in _FALLBACK_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())

    raise RuntimeError(
        "Cannot find the Cursor `agent` binary.\n\n"
        "Tried:\n"
        "  - CURSOR_AGENT_PATH env var (not set)\n"
        '  - shutil.which("agent")\n'
        "  - ~/.local/bin/agent, /usr/local/bin/agent, ~/bin/agent,\n"
        "    /opt/homebrew/bin/agent, /usr/bin/agent\n\n"
        "Fix options:\n"
        "  1. Add the directory containing `agent` to PATH, then restart "
        "the MCP server.\n"
        "  2. Set CURSOR_AGENT_PATH=/absolute/path/to/agent in the MCP "
        "server's env config.\n\n"
        "Verify your install: run `agent --version` in a terminal where "
        "it works, then `which agent` to find its location."
    )


_AGENT_BIN: str = _resolve_agent_binary()


@dataclass
class ToolCallEvent:
    tool: str
    args: dict
    status: str  # "started" | "completed"
    result: Optional[dict] = None


@dataclass
class AgentResult:
    text: str
    session_id: str
    model: str
    tool_calls: list[ToolCallEvent]
    usage: dict
    duration_ms: int
    is_error: bool
    error_message: Optional[str] = None


def run_agent(
    prompt: str,
    *,
    session_id: Optional[str] = None,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
    mode: Optional[str] = None,   # "plan" | "ask" | None
    yolo: bool = False,
    timeout: int = 300,
) -> AgentResult:
    cmd = [_AGENT_BIN, "--print", "--output-format", "stream-json", "--trust"]

    if session_id:
        cmd += ["--resume", session_id]
    if workspace:
        cmd += ["--workspace", workspace]
    if model:
        cmd += ["--model", model]
    if mode in ("plan", "ask"):
        cmd += ["--mode", mode]
    if yolo:
        cmd.append("--yolo")

    cmd.append(prompt)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return _parse_stream(proc.stdout, proc.returncode, proc.stderr)


def _parse_stream(output: str, returncode: int, stderr: str) -> AgentResult:
    text = ""
    sid = ""
    model = ""
    usage: dict = {}
    duration_ms = 0
    is_error = returncode != 0
    error_message: Optional[str] = stderr.strip() if is_error else None

    tool_calls_by_id: dict[str, ToolCallEvent] = {}
    ordered_calls: list[ToolCallEvent] = []

    for raw in output.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue

        t = ev.get("type")
        sid = ev.get("session_id", sid)

        if t == "system" and ev.get("subtype") == "init":
            model = ev.get("model", "")

        elif t == "assistant":
            content = ev.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    text += block.get("text", "")

        elif t == "tool_call":
            call_id = ev.get("call_id", "")
            subtype = ev.get("subtype")
            tc_data = ev.get("tool_call", {})

            if subtype == "started":
                # tool name is the only key in tool_call (e.g. readToolCall)
                tool_key = next(iter(tc_data), "")
                tool_name = _normalise_tool_name(tool_key)
                args = tc_data.get(tool_key, {}).get("args", {})
                evt = ToolCallEvent(tool=tool_name, args=args, status="started")
                tool_calls_by_id[call_id] = evt
                ordered_calls.append(evt)

            elif subtype == "completed" and call_id in tool_calls_by_id:
                tool_key = next(iter(tc_data), "")
                result = tc_data.get(tool_key, {}).get("result")
                tool_calls_by_id[call_id].status = "completed"
                tool_calls_by_id[call_id].result = result

        elif t == "result":
            usage = ev.get("usage", {})
            duration_ms = ev.get("duration_ms", 0)
            is_error = ev.get("is_error", is_error)
            if not text:
                text = ev.get("result", "")

    return AgentResult(
        text=text,
        session_id=sid,
        model=model,
        tool_calls=ordered_calls,
        usage=usage,
        duration_ms=duration_ms,
        is_error=is_error,
        error_message=error_message,
    )


def _normalise_tool_name(key: str) -> str:
    # "readToolCall" → "read", "runCommandToolCall" → "run_command"
    name = key.replace("ToolCall", "")
    # camelCase → snake_case
    result = []
    for i, ch in enumerate(name):
        if ch.isupper() and i:
            result.append("_")
        result.append(ch.lower())
    return "".join(result)


def create_session() -> str:
    proc = subprocess.run(
        [_AGENT_BIN, "create-chat"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout.strip()


def list_models() -> list[dict]:
    proc = subprocess.run(
        [_AGENT_BIN, "--list-models"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    models = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if " - " in line and not line.startswith("Available") and not line.startswith("Tip"):
            parts = line.split(" - ", 1)
            models.append({"id": parts[0].strip(), "name": parts[1].strip()})
    return models


def get_status() -> dict:
    proc = subprocess.run(
        [_AGENT_BIN, "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = proc.stdout.strip()
    # "✓ Logged in as user@example.com"
    email = ""
    if "Logged in as" in text:
        email = text.split("Logged in as")[-1].strip()
    return {"authenticated": proc.returncode == 0, "email": email, "raw": text}
