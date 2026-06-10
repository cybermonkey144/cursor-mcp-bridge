"""Shared helpers for the installer CLIs."""

from pathlib import Path


def confirm_overwrite(path: Path) -> bool:
    try:
        reply = input(f"{path} exists. Overwrite? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return reply == "y"
