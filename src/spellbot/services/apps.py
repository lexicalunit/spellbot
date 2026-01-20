from __future__ import annotations

from asgiref.sync import sync_to_async
from ddtrace.trace import tracer

from spellbot.database import DatabaseSession
from spellbot.models import Token


class AppsService:
    @sync_to_async()
    @tracer.wrap()
    def verify_token(self, key: str, path: str) -> bool:
        token = DatabaseSession.query(Token).filter(Token.key == key).one_or_none()
        if not token:
            return False
        if token.deleted_at:
            return False
        if token.scopes == "*":
            return True
        try:
            required_scope = path.lstrip("/").split("/")[1]
        except IndexError:
            return False
        scopes_list = token.scopes.split(",")
        return required_scope in scopes_list
