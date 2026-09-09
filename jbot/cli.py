import json
import threading

from jbot import __version__
from jbot.agent import clear_history, load_history, run_agent, run_agent_loop
from jbot.config import LLM_MODEL, SANDBOX_DIR
from jbot.session import list_sessions, load_session, save_session
from jbot.tools import list_tool_names
from jbot.tools.files import remove_file
from jbot.tools.memory import list_memories, memorize, recall_fact
from jbot.tools.search import web_search
from jbot.ui import (
    ask_input,
    render_banner,
    render_goodbye,
    render_memories,
    render_notice,
    render_reply,
    render_search,
    render_sessions,
    render_tool_event,
    render_user_message,
    print_help,
    TokenStream,
)


def _handle_tool_event(event, pending, stream=None):
    if stream is not None:
        stream.pause()
    kind = event.get("type")
    if kind == "tool_end":
        raw = event.get("result")
        parsed = raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
        if isinstance(parsed, dict) and parsed.get("needs_confirm"):
            pending["delete"] = parsed.get("path")
            render_notice(f"Delete {pending['delete']}? Type y or n", "warn")
            return
    render_tool_event(event)


def _run_turn(text, cancel_event):
    stream = TokenStream()
    pending = {}
    try:
        reply, _, _ = run_agent(
            text,
            on_event=lambda event: _handle_tool_event(event, pending, stream),
            cancel_event=cancel_event,
            on_token=stream.on_token,
        )
        stream.finish(reply)
        return pending.get("delete")
    except KeyboardInterrupt:
        cancel_event.set()
        stream.finish("", show_empty=False)
        render_notice("Cancelled.", "warn")
        return None
    except Exception as exc:
        stream.finish("", show_empty=False)
        render_notice(f"Error: {exc}", "error")
        return None


def _run_plan(goal, cancel_event):
    stream = TokenStream()
    try:
        result = run_agent_loop(
            goal,
            on_event=lambda event: _handle_tool_event(event, {}, stream),
            cancel_event=cancel_event,
            on_token=stream.on_token,
        )
        stream.finish(result)
    except KeyboardInterrupt:
        cancel_event.set()
        stream.finish("", show_empty=False)
        render_notice("Cancelled.", "warn")
    except Exception as exc:
        stream.finish("", show_empty=False)
        render_notice(f"Error: {exc}", "error")


def _handle_command(text):
    lowered = text.lower()
    if lowered in {"/exit", "/quit", "exit", "quit"}:
        return False
    if lowered in {"/help", "help"}:
        print_help(list_tool_names())
        return True
    if lowered == "/tools":
        tools = "\n".join(f"- {name}" for name in list_tool_names())
        render_reply("tools the model can call\n\n" + tools, animate=False)
        return True
    if lowered == "/clear":
        clear_history()
        render_notice("Conversation history cleared.")
        return True
    if lowered == "/mem":
        render_memories(list_memories())
        return True
    if lowered.startswith("/memorize"):
        rest = text[9:].strip()
        key, _, value = rest.partition(" ")
        if not key or not value:
            render_notice("Usage: /memorize <key> <value>", "warn")
            return True
        render_notice(str(memorize(key, value)))
        return True
    if lowered.startswith("/recall"):
        key = text[7:].strip()
        if not key:
            render_notice("Usage: /recall <key>", "warn")
            return True
        render_reply(f"recall {key}\n\n{recall_fact(key)}", animate=False)
        return True
    if lowered == "/sessions":
        render_sessions(list_sessions())
        return True
    if lowered.startswith("/save"):
        name = text[5:].strip()
        result = save_session(name)
        if result.get("ok"):
            render_notice(f"Saved session `{result['name']}` ({result['turns']} messages)")
        else:
            render_notice(result.get("error") or str(result), "error")
        return True
    if lowered.startswith("/load"):
        name = text[5:].strip()
        result = load_session(name)
        if not result.get("ok"):
            render_notice(result.get("error") or str(result), "error")
            return True
        render_notice(f"Loaded session `{result['name']}`")
        for msg in result.get("messages") or []:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                render_user_message(content)
            elif role == "assistant":
                render_reply(content, animate=False)
        return True
    if lowered.startswith("/search"):
        query = text[7:].strip()
        if not query:
            render_notice("Usage: /search <query>", "warn")
            return True
        render_user_message(f"/search {query}")
        try:
            render_search(web_search(query))
        except Exception as exc:
            render_notice(f"Error: {exc}", "error")
        return True
    if lowered.startswith("/plan"):
        goal = text[5:].strip()
        if not goal:
            render_notice("Usage: /plan <goal>", "warn")
            return True
        render_user_message(text)
        cancel_event = threading.Event()
        _run_plan(goal, cancel_event)
        return True
    return None


def _restore_history():
    for msg in load_history():
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            render_user_message(content)
        elif role == "assistant":
            render_reply(content, animate=False)


def main():
    render_banner(version=__version__, model=LLM_MODEL, sandbox=str(SANDBOX_DIR))
    _restore_history()
    pending_delete = None
    while True:
        try:
            text = ask_input()
        except (KeyboardInterrupt, EOFError):
            render_goodbye()
            return
        if not text:
            continue
        if pending_delete:
            path = pending_delete
            pending_delete = None
            if text.lower() in {"y", "yes"}:
                render_notice(str(remove_file(path, confirm=True)))
            else:
                render_notice(f"Delete cancelled: {path}", "warn")
            continue
        handled = _handle_command(text)
        if handled is False:
            render_goodbye()
            return
        if handled is True:
            continue
        render_user_message(text)
        cancel_event = threading.Event()
        pending_delete = _run_turn(text, cancel_event)


def run():
    main()


if __name__ == "__main__":
    main()
