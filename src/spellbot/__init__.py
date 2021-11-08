from ._version import __version__
from .cli import main
from .client import SpellBot, build_bot

__all__ = [
    "__version__",
    "build_bot",
    "main",
    "SpellBot",
]
