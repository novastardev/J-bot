from jbot.session import load_session, save_session
from jbot.tools.memory import extract_key_details, memorize, recall_fact
from jbot.tools.calc import calculate
from jbot.tools.files import create_file, list_files, read_file, remove_file
from jbot.tools.registry import execute_tool, get_tool_definitions
from jbot.tools.search import web_fetch
from jbot.tools.shell import run_shell


def test_calculate_basic():
    result = calculate("(3 + 5) * 2")
    assert result["result"] == 16


def test_calculate_rejects_names():
    result = calculate("__import__('os').getcwd()")
    assert "error" in result


def test_file_roundtrip(tmp_path, monkeypatch):
    import jbot.tools.files as files

    monkeypatch.setattr(files, "SANDBOX_DIR", tmp_path)
    create_file("notes.txt", "hello")
    assert read_file("notes.txt") == "hello"
    listing = list_files(".")
    names = [item["name"] for item in listing["entries"]]
    assert "notes.txt" in names


def test_remove_file_requires_confirm(tmp_path, monkeypatch):
    import jbot.tools.files as files

    monkeypatch.setattr(files, "SANDBOX_DIR", tmp_path)
    create_file("drop.txt", "x")
    blocked = remove_file("drop.txt")
    assert blocked["needs_confirm"] is True
    assert (tmp_path / "drop.txt").exists()
    done = remove_file("drop.txt", confirm=True)
    assert "Removed" in done
    assert not (tmp_path / "drop.txt").exists()


def test_shell_blocks_and_runs(tmp_path, monkeypatch):
    import jbot.tools.shell as shell

    monkeypatch.setattr(shell, "SANDBOX_DIR", tmp_path)
    blocked = run_shell("sudo ls")
    assert "error" in blocked
    ok = run_shell("echo hi")
    assert ok["returncode"] == 0
    assert "hi" in ok["stdout"]


def test_web_fetch_rejects_bad_url():
    result = web_fetch("not-a-url")
    assert "error" in result


def test_sessions(tmp_path, monkeypatch):
    import jbot.session as session
    import jbot.config as config

    monkeypatch.setattr(session, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    (tmp_path / "history.json").write_text('[{"role":"user","content":"hi"}]', encoding="utf-8")
    saved = save_session("demo")
    assert saved["ok"] is True
    (tmp_path / "history.json").write_text("[]", encoding="utf-8")
    loaded = load_session("demo")
    assert loaded["ok"] is True
    assert loaded["messages"][0]["content"] == "hi"


def test_memorize_and_recall(tmp_path, monkeypatch):
    import jbot.tools.memory as memory

    monkeypatch.setattr(memory, "MEMORY_FILE", tmp_path / "memory.json")
    assert "Memorized" in memorize("user_name", "Ada")
    assert recall_fact("user_name") == "Ada"
    extract_key_details([{"role": "user", "content": "Remember my timezone is UTC"}])
    assert "UTC" in recall_fact("timezone")


def test_tool_definitions_exist():
    defs = get_tool_definitions()
    names = {item["function"]["name"] for item in defs}
    assert "calculate" in names
    assert "web_search" in names
    assert "web_fetch" in names
    assert "run_shell" in names
    assert execute_tool("calculate", {"expression": "1+1"}).find("2") != -1
