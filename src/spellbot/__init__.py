# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from ._version import __version__
from .cli import main
from .client import SpellBot

__all__ = [
    "SpellBot",
    "__version__",
    "main",
]
