# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class FactorySession:
    """The session test factories persist objects with, set per test by `session_context`."""

    current: Session | None = None


def factory_session() -> Session:
    """Return the current factory session; used as each factory's `sqlalchemy_session_factory`."""
    if FactorySession.current is None:  # pragma: no cover
        msg = "No session provided."
        raise RuntimeError(msg)
    return FactorySession.current
