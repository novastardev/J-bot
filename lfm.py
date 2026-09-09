"""Compatibility shim. Prefer `from jbot.agent import run_agent`."""

from jbot.agent import run_agent, run_agent_loop
from jbot.llm import chat as generate
from jbot.tools.registry import TOOLS, execute_tool, get_tool_definitions, tool

__all__ = [
    "tool",
    "TOOLS",
    "get_tool_definitions",
    "generate",
    "execute_tool",
    "run_agent",
    "run_agent_loop",
]
