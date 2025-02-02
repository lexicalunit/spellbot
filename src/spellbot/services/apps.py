from __future__ import annotations

from asgiref.sync import sync_to_async
from ddtrace.trace import tracer

from spellbot.database import DatabaseSession
from spellbot.models import Token


class AppsService:
    @sync_to_async()
    @tracer.wrap()
    def verify_token(self, key: str) -> bool:
        return bool(DatabaseSession.query(Token).filter(Token.key == key).count())
