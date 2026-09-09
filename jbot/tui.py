import json
import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, Static

from jbot import __version__
from jbot.agent import clear_history, load_history, run_agent, run_agent_loop
from jbot.config import LLM_MODEL, SANDBOX_DIR
from jbot.session import list_sessions, load_session, save_session
from jbot.tools import list_tool_names
from jbot.tools.files import remove_file
from jbot.tools.memory import list_memories, memorize, recall_fact
from jbot.tools.search import web_search


HELP_MD = """\
**commands you type**

| Command | Description |
|---|---|
| `/help` | Show this help |
| `/tools` | List available agent tools |
| `/search <query>` | Search the web now |
| `/clear` | Clear conversation history |
| `/mem` | Show stored memories |
| `/memorize <key> <value>` | Keep a fact after context compression |
| `/recall <key>` | Recall a stored fact |
| `/save <name>` | Save this chat session |
| `/load <name>` | Load a saved session |
| `/sessions` | List saved sessions |
| `/plan <goal>` | Plan a goal and run the steps |
| `/exit` | Quit |

Ctrl+C cancels the current run. Ctrl+Q quits.
"""


class UserBubble(Static):
    DEFAULT_CSS = """
    UserBubble {
        border: round green;
        border-title-color: green;
        border-title-align: right;
        color: $text;
        padding: 0 1;
        margin: 0 0 1 8;
        width: 1fr;
        background: transparent;
    }
    """


class BotBubble(Markdown):
    DEFAULT_CSS = """
    BotBubble {
        border: round magenta;
        border-title-color: magenta;
        border-title-align: left;
        padding: 0 1;
        margin: 0 8 1 0;
        width: 1fr;
        background: transparent;
    }
    """


class ToolLine(Static):
    DEFAULT_CSS = """
    ToolLine {
        color: $text-muted;
        padding: 0 2;
        margin: 0 0 1 0;
        width: 1fr;
    }
    """


class StatusLine(Static):
    DEFAULT_CSS = """
    StatusLine {
        color: $text-muted;
        padding: 0 1;
        margin: 0 0 1 0;
        width: 1fr;
    }
    """


def _format_search(result: dict) -> str:
    if not isinstance(result, dict):
        return str(result)
    if result.get("ok"):
        lines = [f"**{result.get('query', '')}** via `{result.get('engine')}`", ""]
        if result.get("answer"):
            lines.append(result["answer"])
            lines.append("")
        for index, source in enumerate(result.get("sources") or [], 1):
            title = source.get("title") or source.get("url") or "source"
            url = source.get("url") or ""
            lines.append(f"{index}. [{title}]({url})" if url else f"{index}. {title}")
        return "\n".join(lines)
    if result.get("error"):
        return f"Search failed: {result.get('error')}"
    return json.dumps(result, indent=2)


class JBotTUI(App):
    TITLE = "J-BOT"
    SUB_TITLE = "Advanced Terminal AI"
    CSS = """
    Screen {
        background: #0b1020;
        color: #e8edf7;
    }

    Header {
        background: #12182c;
        color: #c084fc;
        text-style: bold;
    }

    Footer {
        background: #12182c;
        color: #93a0bc;
    }

    #meta {
        color: #93a0bc;
        padding: 0 2;
        height: 1;
        dock: top;
    }

    #chat {
        padding: 1 1 0 1;
        height: 1fr;
    }

    #composer {
        dock: bottom;
        height: auto;
        padding: 0 1 1 1;
        background: #0b1020;
    }

    #you-label {
        width: 6;
        color: #34d399;
        text-style: bold;
        content-align: right middle;
        padding: 0 1 0 0;
    }

    #input {
        border: round green;
        background: #12182c;
        color: #e8edf7;
        padding: 0 1;
    }

    #input:focus {
        border: round green;
    }
    """
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Cancel", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("escape", "interrupt", "Cancel", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
    ]

    def __init__(self):
        super().__init__()
        self._busy = False
        self._cancel = threading.Event()
        self._stream_bubble = None
        self._stream_text = ""
        self._pending_delete = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(self._meta_text(), id="meta")
        yield VerticalScroll(id="chat")
        with Horizontal(id="composer"):
            yield Static("you", id="you-label")
            yield Input(placeholder="message or /help", id="input")
        yield Footer()

    def _meta_text(self) -> str:
        return f"v{__version__}  ·  Model: {LLM_MODEL}  ·  Sandbox: {SANDBOX_DIR}"

    def on_mount(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        intro = BotBubble("J-BOT is running and ready to build.\n\nType a request, or `/help` for commands.")
        intro.border_title = "J-BOT"
        chat.mount(intro)
        self._restore_history(chat)
        self.query_one("#input", Input).focus()

    def _restore_history(self, chat: VerticalScroll, messages=None) -> None:
        for msg in messages if messages is not None else load_history():
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                self._add_user(chat, content)
            elif role == "assistant":
                self._add_bot(chat, content)

    def _add_user(self, chat: VerticalScroll, text: str) -> UserBubble:
        bubble = UserBubble(text)
        bubble.border_title = "you"
        chat.mount(bubble)
        chat.scroll_end(animate=False)
        return bubble

    def _add_bot(self, chat: VerticalScroll, text: str) -> BotBubble:
        bubble = BotBubble(text or "(no reply)")
        bubble.border_title = "J-BOT"
        chat.mount(bubble)
        chat.scroll_end(animate=False)
        return bubble

    def _add_status(self, chat: VerticalScroll, text: str) -> StatusLine:
        line = StatusLine(text)
        chat.mount(line)
        chat.scroll_end(animate=False)
        return line

    def _add_tool(self, chat: VerticalScroll, text: str) -> ToolLine:
        line = ToolLine(text)
        chat.mount(line)
        chat.scroll_end(animate=False)
        return line

    def _on_token(self, chat: VerticalScroll, piece: str) -> None:
        if not piece:
            return
        if self._stream_bubble is None:
            self._stream_text = ""
            self._stream_bubble = self._add_bot(chat, "")
        self._stream_text += piece
        self._stream_bubble.update(self._stream_text)
        chat.scroll_end(animate=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if not text:
            return
        chat = self.query_one("#chat", VerticalScroll)
        if self._pending_delete:
            self._handle_delete_confirm(text, chat)
            return
        if self._busy:
            return
        handled = self._handle_command(text, chat)
        if handled is False:
            self.exit()
            return
        if handled is True:
            return
        self._add_user(chat, text)
        self._start_busy("thinking...")
        self.run_worker(self._run_turn(text, chat), exclusive=True, thread=True)

    def _handle_delete_confirm(self, text: str, chat: VerticalScroll) -> None:
        path = self._pending_delete
        self._pending_delete = None
        lowered = text.lower()
        if lowered in {"y", "yes"}:
            result = remove_file(path, confirm=True)
            self._add_status(chat, str(result))
        else:
            self._add_status(chat, f"Delete cancelled: {path}")

    def _handle_command(self, text: str, chat: VerticalScroll):
        lowered = text.lower()
        if lowered in {"/exit", "/quit", "exit", "quit"}:
            return False
        if lowered in {"/help", "help"}:
            tools = ", ".join(list_tool_names())
            self._add_bot(chat, HELP_MD + f"\n\n`{tools}`")
            return True
        if lowered == "/tools":
            tools = "\n".join(f"- `{name}`" for name in list_tool_names())
            self._add_bot(chat, "**tools the model can call**\n\n" + tools)
            return True
        if lowered == "/clear":
            self.action_clear_chat()
            return True
        if lowered == "/mem":
            payload = list_memories()
            self._add_bot(chat, f"**memory**\n\n```\n{payload}\n```")
            return True
        if lowered.startswith("/memorize"):
            rest = text[9:].strip()
            key, _, value = rest.partition(" ")
            if not key or not value:
                self._add_status(chat, "Usage: /memorize <key> <value>")
                return True
            self._add_status(chat, str(memorize(key, value)))
            return True
        if lowered.startswith("/recall"):
            key = text[7:].strip()
            if not key:
                self._add_status(chat, "Usage: /recall <key>")
                return True
            self._add_bot(chat, f"**recall `{key}`**\n\n{recall_fact(key)}")
            return True
        if lowered == "/sessions":
            rows = list_sessions()
            if not rows:
                self._add_status(chat, "No saved sessions.")
                return True
            lines = ["**sessions**", ""]
            for row in rows:
                lines.append(f"- `{row['name']}`  {row['updated']}")
            self._add_bot(chat, "\n".join(lines))
            return True
        if lowered.startswith("/save"):
            name = text[5:].strip()
            result = save_session(name)
            if result.get("ok"):
                self._add_status(chat, f"Saved session `{result['name']}` ({result['turns']} messages)")
            else:
                self._add_status(chat, result.get("error") or str(result))
            return True
        if lowered.startswith("/load"):
            name = text[5:].strip()
            result = load_session(name)
            if not result.get("ok"):
                self._add_status(chat, result.get("error") or str(result))
                return True
            chat.remove_children()
            self._restore_history(chat, result.get("messages"))
            self._add_status(chat, f"Loaded session `{result['name']}`")
            return True
        if lowered.startswith("/search"):
            query = text[7:].strip()
            if not query:
                self._add_status(chat, "Usage: /search <query>")
                return True
            self._add_user(chat, f"/search {query}")
            self._start_busy("searching...")
            self.run_worker(self._run_search(query, chat), exclusive=True, thread=True)
            return True
        if lowered.startswith("/plan "):
            goal = text[6:].strip()
            if not goal:
                self._add_status(chat, "Usage: /plan <goal>")
                return True
            self._add_user(chat, text)
            self._start_busy("planning...")
            self.run_worker(self._run_plan(goal, chat), exclusive=True, thread=True)
            return True
        return None

    def _ask_delete(self, chat: VerticalScroll, path: str) -> None:
        self._pending_delete = path
        self._add_status(chat, f"Delete {path}? Type y or n")

    def _start_busy(self, placeholder: str) -> None:
        self._busy = True
        self._cancel = threading.Event()
        self._stream_bubble = None
        self._stream_text = ""
        field = self.query_one("#input", Input)
        field.placeholder = placeholder + "  (Ctrl+C cancel)"

    def _on_event(self, chat: VerticalScroll, event: dict) -> None:
        kind = event.get("type")
        if kind == "tool_start":
            self.call_from_thread(self._add_tool, chat, f"▸  {event.get('name')}")
        elif kind == "tool_end":
            name = event.get("name")
            raw = event.get("result")
            parsed = raw
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
            if isinstance(parsed, dict) and parsed.get("needs_confirm"):
                path = parsed.get("path")
                self.call_from_thread(self._ask_delete, chat, path)
                return
            result = str(raw or "").replace("\n", " ")
            if len(result) > 120:
                result = result[:117] + "..."
            self.call_from_thread(self._add_tool, chat, f"✓  {name}  {result}")
        elif kind == "error":
            self.call_from_thread(self._add_status, chat, str(event.get("message") or "error"))
        elif kind == "cancelled":
            self.call_from_thread(self._add_status, chat, "Cancelled.")
        elif kind == "plan":
            self.call_from_thread(self._add_bot, chat, event.get("text") or "")
        elif kind == "step":
            self.call_from_thread(
                self._add_status,
                chat,
                f"step {event.get('index')}/{event.get('total')}  {event.get('text')}",
            )

    def _run_turn(self, text: str, chat: VerticalScroll) -> None:
        try:
            reply, _, _ = run_agent(
                text,
                on_event=lambda event: self._on_event(chat, event),
                cancel_event=self._cancel,
                on_token=lambda piece: self.call_from_thread(self._on_token, chat, piece),
            )
            if self._stream_bubble is None:
                self.call_from_thread(self._add_bot, chat, reply or "(no reply)")
        finally:
            self.call_from_thread(self._idle)

    def _run_plan(self, goal: str, chat: VerticalScroll) -> None:
        try:
            result = run_agent_loop(
                goal,
                on_event=lambda event: self._on_event(chat, event),
                cancel_event=self._cancel,
                on_token=lambda piece: self.call_from_thread(self._on_token, chat, piece),
            )
            if self._stream_bubble is None:
                self.call_from_thread(self._add_bot, chat, result or "(no reply)")
        finally:
            self.call_from_thread(self._idle)

    def _run_search(self, query: str, chat: VerticalScroll) -> None:
        try:
            result = web_search(query)
            self.call_from_thread(self._add_bot, chat, _format_search(result))
        finally:
            self.call_from_thread(self._idle)

    def _idle(self) -> None:
        self._busy = False
        self._stream_bubble = None
        field = self.query_one("#input", Input)
        field.placeholder = "message or /help"
        field.focus()

    def action_interrupt(self) -> None:
        if self._busy:
            self._cancel.set()
            chat = self.query_one("#chat", VerticalScroll)
            self._add_status(chat, "Cancelling...")
            return
        self.exit()

    def action_clear_chat(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        clear_history()
        chat.remove_children()
        self._add_status(chat, "Conversation history cleared.")


def run() -> None:
    JBotTUI().run()
