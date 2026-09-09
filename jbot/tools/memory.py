import json
import re
from datetime import datetime

from jbot.config import MEMORY_FILE
from jbot.tools.registry import tool

MAX_FACTS = 40
MAX_VALUE = 400


def _load_memory():
    if MEMORY_FILE.exists():
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_memory(data):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_key(key: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (key or "").strip().lower())
    return cleaned.strip("_")[:48] or "note"


def _entry_text(item):
    if isinstance(item, dict):
        return str(item.get("value", "")).strip()
    return str(item).strip()


def memory_prompt():
    data = _load_memory()
    if not data:
        return ""
    lines = []
    for key, value in data.items():
        text = _entry_text(value)
        if not text:
            continue
        lines.append(f"- {key}: {text}")
    if not lines:
        return ""
    return (
        "\nPermanent memories (survive the 20-message context window; "
        "use recall(key) if you need one later):\n"
        + "\n".join(lines[:MAX_FACTS])
    )


def memorize(key: str, value: str):
    """Store a durable fact that survives context compression."""
    safe_key = _normalize_key(key)
    text = " ".join((value or "").split())[:MAX_VALUE]
    if not text:
        return {"error": "Nothing to memorize."}
    data = _load_memory()
    data[safe_key] = {
        "value": text,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if len(data) > MAX_FACTS:
        oldest = sorted(data.items(), key=lambda item: _updated_at(item[1]))[: len(data) - MAX_FACTS]
        for drop_key, _ in oldest:
            if drop_key != safe_key:
                del data[drop_key]
    _save_memory(data)
    return f"Memorized '{safe_key}'."


def _updated_at(item):
    if isinstance(item, dict):
        return item.get("updated_at") or ""
    return ""


def recall_fact(key: str):
    data = _load_memory()
    if key in data:
        return _entry_text(data[key]) or f"No memory found for key '{key}'."
    safe = _normalize_key(key)
    if safe in data:
        return _entry_text(data[safe])
    matches = []
    needle = (key or "").lower()
    for stored_key, item in data.items():
        text = _entry_text(item)
        if needle in stored_key.lower() or needle in text.lower():
            matches.append(f"{stored_key}: {text}")
    if matches:
        return "\n".join(matches[:8])
    return f"No memory found for key '{key}'."


def extract_key_details(messages):
    """Pull durable facts from messages about to fall out of the 20-message window."""
    saved = []
    for item in messages:
        if item.get("role") != "user":
            continue
        text = (item.get("content") or "").strip()
        if not text or text.startswith("/"):
            continue
        for pattern, key in (
            (r"(?:my name is|i am|i'm)\s+([A-Za-z][A-Za-z0-9._-]{1,40})", "user_name"),
            (r"(?:call me)\s+([A-Za-z][A-Za-z0-9._-]{1,40})", "user_name"),
            (r"(?:i live in|i'm from|i am from)\s+(.{2,60})", "user_location"),
            (r"(?:my timezone is|timezone[:\s]+)\s*([A-Za-z0-9_+\-/]{2,40})", "timezone"),
            (r"(?:prefer|please use)\s+(.{2,80})", "preference"),
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                memorize(key, match.group(1).strip(" .,!"))
                saved.append(key)
        if re.search(r"\b(remember|memorize|don't forget|keep in mind)\b", text, flags=re.IGNORECASE):
            memorize("session_note", text)
            saved.append("session_note")
    return saved


@tool
def remember(key: str, value: str):
    """
    Store a fact under a short key so it survives context compression.

    Use this when the user asks you to remember something, or when you learn
    a reusable fact (name, preference, project, constraint).

    Args:
        key:   A short, stable name for the fact (e.g. "user_name").
        value: The fact itself.
    """
    return memorize(key, value)


@tool
def recall(key: str):
    """
    Recall a previously stored fact by key, even if it dropped out of chat history.

    Args:
        key: The exact key, or a word to search in stored memories.
    """
    return recall_fact(key)


@tool
def forget(key: str):
    """
    Delete a stored fact by its key.

    Args:
        key: The exact key to remove.
    """
    data = _load_memory()
    safe = key if key in data else _normalize_key(key)
    if safe in data:
        del data[safe]
        _save_memory(data)
        return f"Forgot '{safe}'."
    return f"No memory found for key '{key}'."


@tool
def list_memories():
    """Return every stored memory as a JSON object. Use when the user asks what you remember."""
    data = _load_memory()
    if not data:
        return "No memories stored yet."
    return json.dumps(data, indent=2, ensure_ascii=False)
