"""MCP server exposing Cursor's agent CLI as tools."""

from typing import Optional
import fastmcp
from agent_runner import run_agent, create_session as _create_session, list_models, get_status
import session_store

DEFAULT_MODEL = "auto"

mcp = fastmcp.FastMCP(
    name="cursor-agent",
    instructions=(
        "Tools for delegating tasks to Cursor's AI agent. "
        "The agent has full access to the filesystem, shell, and web within the target workspace. "
        "Use create_session + send_message for multi-turn work. "
        "Use run for quick one-shot tasks. "
        "Use plan to get a read-only analysis before committing to edits."
    ),
)


# ---------------------------------------------------------------------------
# One-shot tools
# ---------------------------------------------------------------------------

@mcp.tool
def run(
    prompt: str,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
    yolo: bool = False,
) -> dict:
    """
    Send a single prompt to the Cursor agent and get a response.

    The agent has full tool access: file read/write, shell commands, web search.
    No session is created — use this for standalone tasks.

    Args:
        prompt: The instruction or question for the agent.
        workspace: Absolute path to the directory the agent should work in.
                   Defaults to the MCP server's working directory.
        model: Model ID to use (e.g. 'claude-opus-4-7-high'). Omit for default.
        yolo: If true, the agent auto-approves all its own tool calls (shell commands etc.).
    """
    result = run_agent(prompt, workspace=workspace, model=model or DEFAULT_MODEL, yolo=yolo)
    return _serialise(result)


@mcp.tool
def plan(
    prompt: str,
    session_id: Optional[str] = None,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Run the Cursor agent in plan mode — read-only analysis, no file edits.

    Use this to get a detailed proposal or analysis before committing to changes.

    Args:
        prompt: What to analyze or plan.
        session_id: Existing session to continue within (optional).
        workspace: Directory the agent should read from.
        model: Model ID override.
    """
    result = run_agent(prompt, session_id=session_id, workspace=workspace, model=model or DEFAULT_MODEL, mode="plan")
    if session_id:
        session_store.touch_session(session_id)
    return _serialise(result)


@mcp.tool
def ask(
    prompt: str,
    session_id: Optional[str] = None,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Run the Cursor agent in ask mode — Q&A only, no tools, fastest response.

    Use for explanations, questions about code, or anything that doesn't need
    the agent to touch files or run commands.

    Args:
        prompt: Your question.
        session_id: Existing session to continue within (optional).
        workspace: Directory context (the agent won't edit, but can reference).
        model: Model ID override.
    """
    result = run_agent(prompt, session_id=session_id, workspace=workspace, model=model or DEFAULT_MODEL, mode="ask")
    if session_id:
        session_store.touch_session(session_id)
    return _serialise(result)


# ---------------------------------------------------------------------------
# Session tools
# ---------------------------------------------------------------------------

@mcp.tool
def create_session(
    label: str = "",
    workspace: Optional[str] = None,
) -> dict:
    """
    Create a new persistent Cursor agent session.

    Returns a session_id that you can pass to send_message for multi-turn
    conversations. Sessions persist across MCP server restarts.

    Args:
        label: Human-readable name to identify this session later.
        workspace: Directory this session will primarily work in.
    """
    sid = _create_session()
    if not sid:
        return {"error": "Failed to create session — is the agent CLI installed and authenticated?"}
    session_store.save_session(sid, label=label, workspace=workspace or "")
    return {"session_id": sid, "label": label, "workspace": workspace or ""}


@mcp.tool
def send_message(
    session_id: str,
    prompt: str,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
    yolo: bool = False,
) -> dict:
    """
    Send a message to an existing Cursor agent session.

    The agent remembers the full conversation history for this session.
    Use create_session first to get a session_id.

    Args:
        session_id: UUID returned by create_session.
        prompt: Your next message or instruction.
        workspace: Override the working directory for this turn.
        model: Model ID override for this turn.
        yolo: Auto-approve all agent tool calls.
    """
    result = run_agent(prompt, session_id=session_id, workspace=workspace, model=model or DEFAULT_MODEL, yolo=yolo)
    session_store.touch_session(session_id)
    return _serialise(result)


@mcp.tool
def list_sessions() -> list[dict]:
    """
    List all saved Cursor agent sessions, most recently used first.

    Returns session_id, label, workspace, created_at, and last_used timestamps.
    """
    return session_store.list_sessions()


@mcp.tool
def delete_session(session_id: str) -> dict:
    """
    Remove a session from local storage.

    This only removes the local record — the session history on Cursor's side
    is unaffected and can still be resumed by ID if you have it elsewhere.

    Args:
        session_id: UUID of the session to remove.
    """
    removed = session_store.delete_session(session_id)
    return {"deleted": removed, "session_id": session_id}


# ---------------------------------------------------------------------------
# Introspection tools
# ---------------------------------------------------------------------------

@mcp.tool
def available_models() -> list[dict]:
    """
    List all models available to the current Cursor account.

    Returns a list of {id, name} objects. Pass the id to the model parameter
    of run, plan, ask, or send_message.
    """
    return list_models()


@mcp.tool
def agent_status() -> dict:
    """
    Check Cursor agent authentication status.

    Returns whether the CLI is authenticated and the logged-in email.
    """
    return get_status()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialise(result) -> dict:
    return {
        "text": result.text,
        "session_id": result.session_id,
        "model": result.model,
        "tool_calls": [
            {
                "tool": tc.tool,
                "args": tc.args,
                "status": tc.status,
                "result": tc.result,
            }
            for tc in result.tool_calls
        ],
        "usage": result.usage,
        "duration_ms": result.duration_ms,
        "is_error": result.is_error,
        **({"error_message": result.error_message} if result.error_message else {}),
    }


if __name__ == "__main__":
    mcp.run()
