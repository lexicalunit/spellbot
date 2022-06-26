from __future__ import annotations

from ._version import __version__
from .cli import main
from .client import SpellBot

__all__ = [
    "__version__",
    "main",
    "SpellBot",
]
