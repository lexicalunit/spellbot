from __future__ import annotations

from ddtrace.trace import tracer
from sqlalchemy import select

from spellbot.database import DatabaseSession
from spellbot.models import Token


class AppsService:
    @tracer.wrap()
    async def verify_token(self, key: str, path: str) -> bool:
        result = await DatabaseSession.execute(select(Token).where(Token.key == key))
        token = result.scalar_one_or_none()
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
