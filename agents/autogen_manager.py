"""
AutoGen Orchestration Manager

Builds a GroupChat with our role agents, registers tools, and runs a session
for a single user prompt. Persists plan/logs via StateStore if desired.

Phase 1: simple single-shot run (no interactive resume). Pause semantics are
honored in selection policy but we exit when a pause is requested.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from core.autogen.state_store import StateStore
from core.autogen.speaker_selection import decide_next, initial_speaker, USER
from core.logger import logger

from .autogen_agents import create_agents, register_registry_tools

try:
    from autogen import GroupChat, GroupChatManager
except Exception as e:
    GroupChat = None  # type: ignore
    GroupChatManager = None  # type: ignore
    logger.warning("AutoGen not available: %s", e)


def _extract_markdown(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Heuristic: return the last assistant content that looks like markdown or non-empty text."""
    for m in reversed(messages or []):
        role = (m.get("role") or "").lower()
        content = m.get("content")
        if isinstance(content, list):
            # content may be a list of parts; pick text parts safely
            parts: List[str] = []
            for p in content:
                if isinstance(p, dict):
                    t = p.get("text")
                    if isinstance(t, str) and t:
                        parts.append(t)
            text = "\n".join(parts)
        else:
            text = str(content or "")
        if role in ("assistant", "system") and text.strip():
            return text
    return None


def _to_messages(gc_manager) -> List[Dict[str, Any]]:
    try:
        # AutoGen managers expose chat_history or chat_messages depending on version
        msgs = getattr(gc_manager, "chat_messages", None)
        if msgs is None:
            msgs = getattr(gc_manager, "chat_history", [])
        # Normalize if it's a dict per agent
        if isinstance(msgs, dict):
            out: List[Dict[str, Any]] = []
            for k, v in msgs.items():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            out.append(item)
            return out
        if isinstance(msgs, list):
            return msgs
    except Exception:
        pass
    return []


def _speaker_selector(last_speaker, groupchat):  # signature expected by AutoGen
    try:
        last_msg = groupchat.messages[-1]["content"] if groupchat.messages else ""
    except Exception:
        last_msg = ""
    # available roles are agent names in this group
    roles = [a.name for a in getattr(groupchat, "agents", [])]
    decision = decide_next(getattr(last_speaker, "name", None), last_msg, available_roles=roles)
    # Find agent object by decided name
    for a in getattr(groupchat, "agents", []):
        if a.name == decision.next_speaker:
            # Attach pause flag on groupchat for the manager to read
            setattr(groupchat, "_should_pause", decision.pause)
            return a
    # fallback: orchestra or first agent
    for a in getattr(groupchat, "agents", []):
        if a.name == "orchestra":
            setattr(groupchat, "_should_pause", False)
            return a
    setattr(groupchat, "_should_pause", False)
    return getattr(groupchat, "agents", [None])[0]


def run_session(prompt: str, *, options: Optional[Dict[str, Any]] = None, job_id: Optional[str] = None,
                human_input_mode: str = "NEVER", max_round: int = 12, persist: bool = True) -> Dict[str, Any]:
    """Run an AutoGen group chat for a single prompt and return a state dict."""
    if GroupChat is None or GroupChatManager is None:
        raise RuntimeError("AutoGen not installed or import failed")

    job_id = job_id or str(uuid.uuid4())
    options = options or {}
    store = StateStore()

    # Build agents and register tools
    agents = create_agents(human_input_mode=human_input_mode)
    register_registry_tools(agents)

    # Compose initial user message with optional options JSON for context
    user_msg = prompt
    if options:
        try:
            import json
            user_msg += "\n\n[options]\n" + json.dumps(options, ensure_ascii=False)
        except Exception:
            pass

    # Group chat with custom speaker selection
    gc = GroupChat(
        agents=[agents["user"], agents["orchestra"], agents["lesson"], agents["assessment"], agents["timetable"], agents["email"]],
        messages=[],
        max_round=max_round,
        speaker_selection_method=_speaker_selector,
    )
    manager = GroupChatManager(groupchat=gc)

    # Kick off conversation
    agents["user"].initiate_chat(manager, message=user_msg)

    # If selection requested a pause (e.g., after specialist), stop here
    paused = bool(getattr(gc, "_should_pause", False))

    # Collect messages and build state
    messages = _to_messages(manager)
    assistant_md = _extract_markdown(messages) or ""

    state: Dict[str, Any] = {
        "job_id": job_id,
        "request": prompt,
        "options": options,
        "state": {"status": "paused" if paused else "succeeded"},
        "checkpoints": [],
        "logs": [],
        "messages": messages[-50:],  # keep tail to limit size
        "assistant_markdown": assistant_md,
        "metadata": {"created_at": None, "updated_at": None},
    }

    # Persist minimal plan-like record
    if persist:
        try:
            store.save_plan(job_id, state)
        except Exception as e:
            logger.warning("StateStore save failed: %s", e)

    return state


__all__ = [
    "run_session",
]
