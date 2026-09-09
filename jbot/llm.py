import json

import requests

from jbot.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, REQUEST_TIMEOUT, TEMPERATURE
from jbot.tools.registry import get_tool_definitions


class LLMError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


def _headers():
    return {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }


def _require_key():
    if not LLM_API_KEY:
        raise LLMError(
            "No API key configured. Set USER_LLM_API_KEY in your .env file "
            "(see .env.example)."
        )


def _payload(messages, tools=None, tool_choice="auto", stream=False):
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    return payload


def chat(messages, tools=None, tool_choice="auto", cancel_event=None):
    _require_key()
    url = f"{LLM_BASE_URL}/chat/completions"
    try:
        response = requests.post(
            url,
            headers=_headers(),
            json=_payload(messages, tools, tool_choice, stream=False),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout as exc:
        raise LLMError("API request timed out. The service may be slow or unreachable.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise LLMError("Could not connect to the LLM API. Check the base URL and network.") from exc

    if cancel_event is not None and cancel_event.is_set():
        raise Cancelled("Cancelled.")
    if response.status_code != 200:
        raise LLMError(f"API error {response.status_code}: {response.text[:300]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected API response: {json.dumps(data)[:300]}") from exc


def _merge_tool_delta(bucket, delta_calls):
    for item in delta_calls or []:
        index = item.get("index", 0)
        current = bucket.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if item.get("id"):
            current["id"] = item["id"]
        if item.get("type"):
            current["type"] = item["type"]
        func = item.get("function") or {}
        if func.get("name"):
            current["function"]["name"] += func["name"]
        if func.get("arguments"):
            current["function"]["arguments"] += func["arguments"]


def chat_stream(messages, tools=None, tool_choice="auto", on_token=None, cancel_event=None):
    _require_key()
    url = f"{LLM_BASE_URL}/chat/completions"
    try:
        response = requests.post(
            url,
            headers=_headers(),
            json=_payload(messages, tools, tool_choice, stream=True),
            timeout=REQUEST_TIMEOUT,
            stream=True,
        )
    except requests.exceptions.Timeout as exc:
        raise LLMError("API request timed out. The service may be slow or unreachable.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise LLMError("Could not connect to the LLM API. Check the base URL and network.") from exc

    if response.status_code != 200:
        raise LLMError(f"API error {response.status_code}: {response.text[:300]}")

    content = ""
    tool_bucket = {}
    for raw in response.iter_lines(decode_unicode=True):
        if cancel_event is not None and cancel_event.is_set():
            response.close()
            raise Cancelled("Cancelled.")
        if not raw:
            continue
        if raw.startswith("data:"):
            raw = raw[5:].strip()
        if raw == "[DONE]":
            break
        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content") or ""
        if piece:
            content += piece
            if on_token:
                on_token(piece)
        _merge_tool_delta(tool_bucket, delta.get("tool_calls"))

    message = {"role": "assistant", "content": content or None}
    if tool_bucket:
        message["tool_calls"] = [tool_bucket[i] for i in sorted(tool_bucket)]
    return message


def default_tools():
    return get_tool_definitions()
