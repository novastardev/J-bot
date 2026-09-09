import datetime
import json
import re
import threading

from jbot.config import HISTORY_FILE, HISTORY_LIMIT, LLM_BASE_URL, LLM_MODEL, MAX_STEPS, SANDBOX_DIR
from jbot.llm import Cancelled, LLMError, chat, chat_stream, default_tools
from jbot.tools.memory import extract_key_details, memory_prompt
from jbot.tools.registry import execute_tool


def system_prompt():
    facts = memory_prompt()
    return (
        "You are J-bot, a capable AI assistant with tools for files, memory, "
        "web search, page fetch, weather, news, GitHub, Wikipedia, translation, "
        "stocks, math, sandbox shell, and system information.\n"
        f"Model: {LLM_MODEL} at {LLM_BASE_URL}.\n"
        f"Sandbox directory: {SANDBOX_DIR}\n"
        f"Current date/time: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
        "Use tools when they improve the answer. Prefer tools over guessing "
        "facts, prices, weather, or file contents.\n"
        "For deletes, call remove_file without confirm first, then only confirm=true "
        "after the user clearly says yes.\n"
        "After tool results, give a clear final answer. Do not mention internal "
        "tool syntax. If a tool fails, explain the error and suggest a next step.\n"
        "Chat history is capped at 20 follow-up messages. Durable facts live in "
        "memory. When the user says remember/memorize, call remember(). When you "
        "need an old detail that is not in the recent chat, call recall(key)."
        f"{facts}"
    )


def _followup_messages(messages):
    kept = []
    for item in messages:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if not content:
            continue
        kept.append({"role": role, "content": content})
    return kept[-HISTORY_LIMIT:]


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return _followup_messages(data if isinstance(data, list) else [])
    except (json.JSONDecodeError, OSError):
        return []


def save_history(messages):
    followup = [
        {"role": item.get("role"), "content": item.get("content")}
        for item in messages
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    trimmed = followup[-HISTORY_LIMIT:]
    dropped = followup[:-HISTORY_LIMIT] if len(followup) > HISTORY_LIMIT else []
    if dropped:
        extract_key_details(dropped)
    HISTORY_FILE.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_history():
    HISTORY_FILE.write_text("[]", encoding="utf-8")


def _normalize_tool_calls(raw_calls):
    calls = []
    for index, item in enumerate(raw_calls or []):
        func = item.get("function") or {}
        arguments = func.get("arguments") or "{}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append(
            {
                "id": item.get("id") or f"call_{index + 1}",
                "type": "function",
                "function": {
                    "name": func.get("name") or "",
                    "arguments": json.dumps(arguments),
                },
                "_parsed": {"name": func.get("name") or "", "arguments": arguments},
            }
        )
    return calls


def _cancelled(cancel_event):
    return cancel_event is not None and cancel_event.is_set()


def run_agent(
    user_input,
    history=None,
    on_event=None,
    persist=True,
    cancel_event=None,
    on_token=None,
):
    events = []

    def emit(event):
        events.append(event)
        if on_event:
            on_event(event)

    if _cancelled(cancel_event):
        return "Cancelled.", events, []

    messages = [{"role": "system", "content": system_prompt()}]
    prior = history if history is not None else load_history()
    messages.extend(_followup_messages(prior))
    messages.append({"role": "user", "content": user_input})

    tools = default_tools()
    reply = ""
    content = ""

    try:
        for step in range(MAX_STEPS):
            if _cancelled(cancel_event):
                raise Cancelled("Cancelled.")
            if on_token:
                try:
                    message = chat_stream(
                        messages,
                        tools=tools,
                        on_token=on_token,
                        cancel_event=cancel_event,
                    )
                except LLMError:
                    message = chat(messages, tools=tools, cancel_event=cancel_event)
            else:
                message = chat(messages, tools=tools, cancel_event=cancel_event)
            raw_calls = message.get("tool_calls") or []
            content = (message.get("content") or "").strip()
            if not raw_calls:
                reply = content
                messages.append({"role": "assistant", "content": reply})
                break

            calls = _normalize_tool_calls(raw_calls)
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function", "function": c["function"]}
                        for c in calls
                    ],
                }
            )
            for call in calls:
                if _cancelled(cancel_event):
                    raise Cancelled("Cancelled.")
                name = call["_parsed"]["name"]
                arguments = call["_parsed"]["arguments"]
                emit({"type": "tool_start", "name": name, "arguments": arguments})
                result = execute_tool(name, arguments)
                emit({"type": "tool_end", "name": name, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": name,
                        "content": result if isinstance(result, str) else str(result),
                    }
                )
        else:
            reply = content or "Stopped after reaching the maximum number of tool steps."
            messages.append({"role": "assistant", "content": reply})
    except Cancelled:
        reply = "Cancelled."
        emit({"type": "cancelled", "message": reply})
        messages.append({"role": "assistant", "content": reply})
    except LLMError as exc:
        reply = str(exc)
        emit({"type": "error", "message": reply})
        messages.append({"role": "assistant", "content": reply})

    if persist and not _cancelled(cancel_event):
        save_history(messages)
    return reply, events, messages


def run_agent_loop(goal, max_steps=5, on_event=None, cancel_event=None, on_token=None):
    if _cancelled(cancel_event):
        return "Cancelled."
    plan_messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous planning agent. Break the goal into a "
                "numbered list of concrete, self-contained steps. Output ONLY "
                "the numbered list, one step per line. Keep it short."
            ),
        },
        {"role": "user", "content": goal},
    ]
    try:
        plan_message = chat(plan_messages, cancel_event=cancel_event)
        plan_text = plan_message.get("content") or ""
    except Cancelled:
        return "Cancelled."
    except LLMError as exc:
        return str(exc)

    if on_event:
        on_event({"type": "plan", "text": plan_text})

    steps = []
    for line in plan_text.splitlines():
        match = re.match(r"^\s*(?:\d+[.)]\s*|[-*]\s+)(.+)$", line.strip())
        if match:
            steps.append(match.group(1))
    if not steps:
        steps = [goal]
    steps = steps[:max_steps]

    context = ""
    last_result = ""
    history = []
    for index, step in enumerate(steps, 1):
        if _cancelled(cancel_event):
            return "Cancelled."
        if on_event:
            on_event({"type": "step", "index": index, "total": len(steps), "text": step})
        prompt = (
            f"Goal: {goal}\n"
            f"Results so far:\n{context or '(none)'}\n\n"
            f"Complete this step only: {step}\n"
            "Use tools if needed. Return a short result for this step."
        )
        last_result, _, history = run_agent(
            prompt,
            history=history,
            persist=False,
            on_event=on_event,
            cancel_event=cancel_event,
            on_token=on_token if index == len(steps) else None,
        )
        if last_result == "Cancelled.":
            return last_result
        context += f"Step {index}: {last_result}\n"
    return last_result


def new_cancel_event():
    return threading.Event()
