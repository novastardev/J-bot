import json
import re
from datetime import datetime
from pathlib import Path

from jbot.config import HISTORY_FILE, HISTORY_LIMIT, SESSIONS_DIR


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip())
    cleaned = cleaned.strip("-._")
    return cleaned[:64]


def _path(name: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{name}.json"


def _read_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_history(messages):
    HISTORY_FILE.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


def list_sessions():
    if not SESSIONS_DIR.exists():
        return []
    rows = []
    for path in sorted(SESSIONS_DIR.glob("*.json")):
        rows.append(
            {
                "name": path.stem,
                "updated": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "size": path.stat().st_size,
            }
        )
    return rows


def save_session(name: str):
    safe = _safe_name(name)
    if not safe:
        return {"error": "Provide a session name, e.g. /save demo"}
    messages = _read_history()
    payload = {
        "name": safe,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "messages": messages,
    }
    path = _path(safe)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "name": safe, "path": str(path), "turns": len(messages)}


def load_session(name: str):
    safe = _safe_name(name)
    if not safe:
        return {"error": "Provide a session name, e.g. /load demo"}
    path = _path(safe)
    if not path.exists():
        return {"error": f"No session named '{safe}'."}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": f"Could not read session: {exc}"}
    messages = payload.get("messages") if isinstance(payload, dict) else payload
    if not isinstance(messages, list):
        messages = []
    followup = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in messages
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ][-HISTORY_LIMIT:]
    _write_history(followup)
    return {"ok": True, "name": safe, "turns": len(followup), "messages": followup}
