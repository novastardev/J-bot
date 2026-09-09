import os
import shutil
from pathlib import Path

from jbot.config import SANDBOX_DIR
from jbot.tools.registry import tool

MAX_READ_BYTES = 200_000


def _resolve(path: str) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = SANDBOX_DIR / target
    resolved = target.resolve()
    sandbox = SANDBOX_DIR.resolve()
    try:
        resolved.relative_to(sandbox)
    except ValueError as exc:
        raise PermissionError(f"Path is outside the sandbox ({sandbox}): {path}") from exc
    return resolved


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


@tool
def create_file(file_name: str, value: str):
    """
    Create or overwrite a text file inside the sandbox.

    Args:
        file_name: Destination filename or relative path.
        value: Exact content to write.
    """
    path = _resolve(file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return {"output": f"Wrote {len(value)} characters to {path}"}


@tool
def read_file(file: str):
    """
    Read and return the contents of an existing text file.

    Args:
        file: Actual filename or relative path inside the sandbox.
    """
    path = _resolve(file)
    if not path.exists():
        return {"error": f"File not found: {file}"}
    if not path.is_file():
        return {"error": f"Not a file: {file}"}
    size = path.stat().st_size
    if size > MAX_READ_BYTES:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
        return text + f"\n\n[truncated; file is {size} bytes]"
    return path.read_text(encoding="utf-8", errors="replace")


@tool
def list_files(directory: str = "."):
    """
    List files and folders in a sandbox directory.

    Args:
        directory: Relative directory path. Defaults to the sandbox root.
    """
    path = _resolve(directory)
    if not path.exists():
        return {"error": f"Directory not found: {directory}"}
    if not path.is_dir():
        return {"error": f"Not a directory: {directory}"}
    entries = []
    for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        kind = "dir" if item.is_dir() else "file"
        size = item.stat().st_size if item.is_file() else None
        entries.append({"name": item.name, "type": kind, "size": size})
    return {"path": str(path), "entries": entries}


@tool
def move_file(original_path: str, location: str):
    """
    Move an existing file inside the sandbox.

    Args:
        original_path: Current file path.
        location: Destination path or directory.
    """
    src = _resolve(original_path)
    dest = _resolve(location)
    if dest.is_dir():
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return f"Moved {src} to {dest}."


@tool
def copy_file(path: str, location: str):
    """
    Copy an existing file inside the sandbox.

    Args:
        path: Source file path.
        location: Destination path or directory.
    """
    src = _resolve(path)
    dest = _resolve(location)
    if dest.is_dir():
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))
    return f"Copied {src} to {dest}."


@tool
def remove_file(file_path: str, confirm: bool = False):
    """
    Delete an existing file inside the sandbox. Requires confirm=true.

    Args:
        file_path: Actual file path. Only delete when the user clearly asked.
        confirm: Must be true after the user explicitly confirms the delete.
    """
    path = _resolve(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if path.is_dir():
        return "Refusing to delete a directory. Provide a file path."
    if not _truthy(confirm):
        return {
            "needs_confirm": True,
            "path": str(path),
            "message": f"Confirm delete of {path}? Ask the user, then call remove_file again with confirm=true only if they say yes.",
        }
    os.remove(path)
    return f"Removed {path}"
