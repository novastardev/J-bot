import random
import shutil
import subprocess
import sys
import time

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich import box
except ImportError:
    print("Missing dependency 'rich'. Install it with: pip install rich")
    sys.exit(1)

console = Console()


def render_banner(version: str = "3.0", model: str = "", sandbox: str = ""):
    console.print(
        Panel.fit(
            "[bold magenta]J-BOT[/bold magenta]  [dim]Advanced Terminal AI[/dim]",
            box=box.DOUBLE,
            border_style="magenta",
        )
    )
    details = []
    if model:
        details.append(f"Model: {model}")
    if sandbox:
        details.append(f"Sandbox: {sandbox}")
    if details:
        console.print(f"[dim]{' · '.join(details)}[/dim]\n")
    console.print("[bold green]J-BOT[/bold green] [dim]is running and ready to build![/dim]")
    console.print("[dim]Type [bold]/help[/bold] for commands. [bold]Ctrl+C[/bold] to quit.[/dim]\n")


def render_user_message(user_input: str):
    console.print(
        Panel(
            user_input,
            title="[bold green]you[/bold green]",
            title_align="right",
            border_style="green",
            box=box.ROUNDED,
        )
    )


def render_reply(reply: str):
    import re as _re

    segments = []
    pos = 0
    fence_re = _re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", _re.DOTALL)
    for m in fence_re.finditer(reply):
        if m.start() > pos:
            prose = reply[pos : m.start()]
            if prose.strip():
                segments.append(("prose", None, prose))
        lang = m.group(1).strip()
        code = m.group(2)
        segments.append(("code", lang, code))
        pos = m.end()
    if pos < len(reply):
        tail = reply[pos:]
        if tail.strip():
            segments.append(("prose", None, tail))

    if not segments:
        segments = [("prose", None, reply)]

    for kind, lang, content in segments:
        if kind == "prose":
            _render_prose_panel(content.strip("\n"))
        else:
            label = lang if lang else "code"
            console.print(f"[dim]— {label} —[/dim]")
            console.print(content.strip("\n"), highlight=False, markup=False)
            console.print(f"[dim]— end {label} —[/dim]")


def _render_prose_panel(text: str):
    if not text:
        return

    out = ""
    panel = Panel(
        out,
        title="[bold magenta]J-BOT[/bold magenta]",
        title_align="left",
        border_style="magenta",
        box=box.ROUNDED,
    )

    with Live(panel, console=console, refresh_per_second=30, transient=False) as live:
        for char in text:
            out += char
            panel = Panel(
                out,
                title="[bold magenta]J-BOT[/bold magenta]",
                title_align="left",
                border_style="magenta",
                box=box.ROUNDED,
            )
            live.update(panel)
            if random.random() < 0.7:
                time.sleep(0.008)
            else:
                time.sleep(0.04)


def render_tool_event(event: dict):
    kind = event.get("type")
    if kind == "tool_start":
        console.print(f"[dim]{event.get('name')}[/dim]")
    elif kind == "tool_end":
        result = str(event.get("result") or "").replace("\n", " ")
        if len(result) > 120:
            result = result[:117] + "..."
        console.print(f"[green]✓ {event.get('name')}[/green] [dim]{result}[/dim]")
    elif kind == "error":
        console.print(f"[red]{event.get('message')}[/red]")
    elif kind == "plan":
        console.print(
            Panel(
                event.get("text") or "",
                title="[bold yellow]plan[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
    elif kind == "step":
        console.print(
            f"[yellow]step {event.get('index')}/{event.get('total')}[/yellow] {event.get('text')}"
        )


def print_help(tool_names=None):
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("Command")
    table.add_column("Description")
    table.add_row("/help", "Show this help")
    table.add_row("/tools", "List available agent tools")
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/mem", "Show stored memories")
    table.add_row("/plan <goal>", "Plan a goal and run the steps")
    table.add_row("/exit", "Quit")
    console.print(table)
    console.print("\n[dim]Press [bold]Ctrl+C[/bold] to quit[/dim]")
    if tool_names:
        console.print(
            "[dim]J-BOT also has tools it uses on its own during a task — this list is just the commands YOU type directly.[/dim]"
        )
        console.print("[dim]" + ", ".join(tool_names) + "[/dim]\n")
    else:
        console.print()


def render_memories(payload: str):
    import json

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        console.print(payload)
        return
    if not data:
        console.print("[yellow]No permanent memory saved yet[/yellow]")
        return
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("Key")
    table.add_column("Value")
    if isinstance(data, dict):
        for key, value in data.items():
            table.add_row(str(key), str(value))
    console.print(table)


def render_notice(message: str, style: str = "ok"):
    color = {"ok": "green", "warn": "yellow", "error": "red"}.get(style, "green")
    console.print(f"[{color}]{message}[/{color}]")


def render_goodbye():
    console.print("\n[dim]Goodbye![/dim]")


def ask_input() -> str:
    return Prompt.ask("[bold green]you[/bold green]").strip()


def send_notification(title: str, message: str, priority: str = "default"):
    try:
        if shutil.which("termux-notification"):
            subprocess.run(
                [
                    "termux-notification",
                    "--title",
                    title,
                    "--content",
                    message[:200],
                    "--priority",
                    priority,
                ],
                check=False,
                timeout=5,
            )
            return
        if shutil.which("notify-send"):
            urgency = "critical" if priority == "high" else "normal"
            subprocess.run(
                ["notify-send", "-u", urgency, title, message[:200]],
                check=False,
                timeout=5,
            )
            return
        console.print(f"[dim]{title}: {message}[/dim]")
    except Exception:
        console.print(f"[dim]{title}: {message}[/dim]")
