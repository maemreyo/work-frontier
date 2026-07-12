"""Baseline public contract for repository bootstrap."""

from typing import Final

HELLO_CONTRACT: Final = "work-frontier"


def hello_contract() -> str:
    """Return the stable bootstrap contract identifier."""
    return HELLO_CONTRACT
