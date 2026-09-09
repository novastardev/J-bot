"""Backward-compatible CLI entry point for J-bot."""

from jbot.cli import main
from jbot.tools.registry import tool  # noqa: F401

if __name__ == "__main__":
    main()
