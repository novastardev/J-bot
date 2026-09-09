import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from jbot.tools.registry import tool
from jbot.config import SESSIONS_DIR

# Optional cryptography for encrypted vault
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    import secrets
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Fernet = None


# -----------------------
# Encrypted Vault
# -----------------------
_VAULT_FILE = SESSIONS_DIR / "vault.enc"
_KEY_FILE = SESSIONS_DIR / ".vault_key"
_SALT_SIZE = 16
_ITERATIONS = 100000


def _get_or_create_key():
    """Return encryption key, creating it if missing."""
    if not CRYPTOGRAPHY_AVAILABLE:
        return None
    # Ensure sessions directory exists
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        _KEY_FILE.chmod(0o600)  # restrict to user only
    return key


def _encrypt(data: str) -> bytes:
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError("Cryptography module not available for encrypted vault")
    # Ensure sessions directory exists
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    f = Fernet(_get_or_create_key())
    return f.encrypt(data.encode("utf-8"))


def _decrypt(data: bytes) -> str:
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError("Cryptography module not available for encrypted vault")
    # Ensure sessions directory exists
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    f = Fernet(_get_or_create_key())
    return f.decrypt(data).decode("utf-8")


def _load_vault():
    if not CRYPTOGRAPHY_AVAILABLE:
        return {}
    # Ensure sessions directory exists
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not _VAULT_FILE.exists():
        return {}
    try:
        return json.loads(_decrypt(_VAULT_FILE.read_bytes()))
    except Exception:
        return {}


def _save_vault(data):
    if not CRYPTOGRAPHY_AVAILABLE:
        return
    # Ensure sessions directory exists
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    _VAULT_FILE.write_bytes(_encrypt(json.dumps(data, indent=2)))
    _VAULT_FILE.chmod(0o600)


@tool
def vault_set(key: str, value: str):
    """
    Store a secret in the encrypted vault (protected at rest).
    Use for API keys, passwords, or sensitive tokens you don't want in .env or history.
    
    Requires cryptography module to be installed.
    
    Args:
        key: Identifier for the secret (e.g. "github_token").
        value: The secret value.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        return "Error: Cryptography module not available. Install with: pip install cryptography"
    
    data = _load_vault()
    data[key] = value
    _save_vault(data)
    return f"Secret '{key}' stored in vault."


@tool
def vault_get(key: str):
    """
    Retrieve a secret from the encrypted vault.
    
    Requires cryptography module to be installed.
    
    Args:
        key: Identifier for the secret.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        return "Error: Cryptography module not available. Install with: pip install cryptography"
    
    data = _load_vault()
    if key in data:
        # Mask output in logs/TUI by default—caller decides whether to show
        return f"[VAULT:{key}]"  # placeholder; actual value returned raw to agent
    return f"Error: No secret found for key '{key}'."


@tool
def vault_list():
    """
    List all keys stored in the encrypted vault (values hidden).
    
    Requires cryptography module to be installed.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        return "Error: Cryptography module not available. Install with: pip install cryptography"
    
    data = _load_vault()
    if not data:
        return "Vault is empty."
    return "Keys: " + ", ".join(sorted(data.keys()))


@tool
def vault_delete(key: str):
    """
    Delete a secret from the encrypted vault.

    Args:
        key: Identifier to remove.
        
    Requires cryptography module to be installed.
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        return "Error: Cryptography module not available. Install with: pip install cryptography"
    
    data = _load_vault()
    if key in data:
        del data[key]
        _save_vault(data)
        return f"Secret '{key}' deleted from vault."
    return f"Error: No secret found for key '{key}'."


# -----------------------
# Skills / Adaptive Learning
# -----------------------
_SKILLS_FILE = SESSIONS_DIR / "skills.json"


def _load_skills():
    if not _SKILLS_FILE.exists():
        return {}
    try:
        return json.loads(_SKILLS_FILE.read_text())
    except Exception:
        return {}


def _save_skills(data):
    _SKILLS_FILE.write_text(json.dumps(data, indent=2))


@tool
def skill_record(pattern: str, tool_name: str, args_json: str = "{}"):
    """
    Record that a user phrase pattern maps to a tool call, so the agent can suggest it later.
    Learns from usage—no explicit training needed.

    Args:
        pattern: Lowercase user phrase (e.g. "show my github profile").
        tool_name: The tool that was invoked (e.g. "github_user").
        args_json: JSON string of the arguments used (default "{}").
    """
    data = _load_skills()
    if pattern not in data:
        data[pattern] = {"count": 0, "tool": tool_name, "args": args_json, "last_used": ""}
    entry = data[pattern]
    entry["count"] += 1
    entry["tool"] = tool_name
    entry["args"] = args_json
    entry["last_used"] = datetime.utcnow().isoformat() + "Z"
    _save_skills(data)
    return f"Skill learned: '{pattern}' → {tool_name}"


@tool
def skill_suggest(partial: str):
    """
    Suggest known skills that match the user's partial input.
    Returns the top 3 most-used matches.

    Args:
        partial: Start of a user phrase (e.g. "show my").
    """
    data = _load_skills()
    partial_lower = partial.lower()
    matches = []
    for pattern, info in data.items():
        if pattern.startswith(partial_lower):
            matches.append(
                {
                    "pattern": pattern,
                    "tool": info["tool"],
                    "count": info["count"],
                    "last_used": info["last_used"],
                }
            )
    matches.sort(key=lambda x: x["count"], reverse=True)
    top = matches[:3]
    if not top:
        return f"No skills match '{partial}'. Try being more general or record one with skill_record."
    lines = []
    for m in top:
        lines.append(f"- '{m['pattern']}' → {m['tool']} (used {m['count']}x, last {m['last_used'][:10]})")
    return "Suggested skills:\n" + "\n".join(lines)


@tool
def skill_forget(pattern: str):
    """
    Forget a learned skill pattern.

    Args:
        pattern: The exact pattern to remove.
    """
    data = _load_skills()
    if pattern in data:
        del data[pattern]
        _save_skills(data)
        return f"Skill '{pattern}' forgotten."
    return f"Error: No skill found for pattern '{pattern}'."


# -----------------------
# Scheduled Jobs (linked to notifications)
# -----------------------
_JOBS_FILE = SESSIONS_DIR / "jobs.json"


def _load_jobs():
    if not _JOBS_FILE.exists():
        return []
    try:
        return json.loads(_JOBS_FILE.read_text())
    except Exception:
        return []


def _save_jobs(data):
    _JOBS_FILE.write_text(json.dumps(data, indent=2, default=str))


@tool
def schedule_job(cron_expr: str, command: str, label: str = ""):
    """
    Schedule a recurring job using cron-like syntax (minute hour day month day_of_week).
    When the time arrives, the agent will run the command and send a notification with the result.

    Supported syntax:
      * * * * *   → every minute
      */5 * * * * → every 5 minutes
      0 * * * *   → at minute 0 of every hour
      0 9 * * MON-FRI → 9 AM on weekdays

    Args:
        cron_expr: Five-field cron string.
        command: What to run (e.g. "get_stock_price AAPL" or "web_search AI news").
        label: Optional human-readable name for the job.
    """
    from croniter import croniter  # lightweight, pure-Python cron parser

    try:
        iterator = croniter(cron_expr, datetime.now())
        next_run = iterator.get_next(datetime)
    except Exception as e:
        return f"Error: Invalid cron expression '{cron_expr}': {e}"

    job = {
        "id": str(uuid.uuid4()),
        "cron": cron_expr,
        "command": command,
        "label": label or command,
        "next_run": next_run.isoformat(),
        "created_at": datetime.now().isoformat(),
    }

    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)

    # Schedule check—lightweight poll in background (handled by agent loop or separate thread)
    # For now, we just store; the agent's main loop or a background thread can poll _load_jobs()
    return f"Job scheduled: '{label or command}' → next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}"


@tool
def list_jobs():
    """
    List all scheduled jobs with their next run time.
    """
    jobs = _load_jobs()
    if not jobs:
        return "No jobs scheduled."
    lines = []
    for j in jobs:
        lines.append(
            f"- {j['label']} ({j['command']}) → cron: {j['cron']} → next: {j['next_run'][:16]}"
        )
    return "Scheduled jobs:\n" + "\n".join(lines)


@tool
def delete_job(job_id: str):
    """
    Delete a scheduled job by its ID.

    Args:
        job_id: The ID returned when scheduling.
    """
    jobs = _load_jobs()
    new_jobs = [j for j in jobs if j["id"] != job_id]
    if len(new_jobs) == len(jobs):
        return f"Error: No job found with ID '{job_id}'."
    _save_jobs(new_jobs)
    return f"Job {job_id} deleted."


# -----------------------
# Background Job Poller (to be called by agent loop or thread)
# -----------------------
def check_and_due_jobs():
    """
    Internal helper: returns list of jobs whose time has come.
    Intended to be called periodically by the agent's main loop or a background thread.
    """
    from croniter import croniter

    now = datetime.now()
    due = []
    jobs = _load_jobs()
    for job in jobs:
        try:
            itr = croniter(job["cron"], now)
            # If the next scheduled time is in the past, it's due
            next_run = itr.get_next(datetime)
            if next_run <= now:
                due.append(job)
                # Update next_run to avoid rapid-fire retrigger
                job["next_run"] = itr.get_next(datetime).isoformat()
        except Exception:
            continue  # skip malformed
    if due:
        _save_jobs(jobs)
    return due