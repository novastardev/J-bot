import shlex
import subprocess

from jbot.config import SANDBOX_DIR
from jbot.tools.registry import tool

BLOCKED = (
    "sudo",
    "su ",
    "reboot",
    "shutdown",
    "poweroff",
    "mkfs",
    "fdisk",
    "iptables",
    "chmod 777 /",
    "rm -rf /",
    "rm -rf /*",
)
TIMEOUT_SEC = 20
MAX_OUTPUT = 12_000


@tool
def run_shell(command: str):
    """
    Run a short shell command inside the sandbox directory.

    Args:
        command: A single shell command. Working directory is the sandbox.
                 No sudo. Output is truncated.
    """
    text = (command or "").strip()
    if not text:
        return {"error": "Empty command."}
    lowered = text.lower()
    for token in BLOCKED:
        if token in lowered:
            return {"error": f"Blocked command: {token.strip()}"}
    try:
        args = shlex.split(text)
    except ValueError as exc:
        return {"error": f"Could not parse command: {exc}"}
    if not args:
        return {"error": "Empty command."}
    try:
        completed = subprocess.run(
            args,
            cwd=str(SANDBOX_DIR),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError:
        return {"error": f"Command not found: {args[0]}"}
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {TIMEOUT_SEC}s."}
    stdout = completed.stdout[-MAX_OUTPUT:]
    stderr = completed.stderr[-MAX_OUTPUT:]
    return {
        "cwd": str(SANDBOX_DIR),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
