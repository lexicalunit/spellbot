from __future__ import annotations

import factory

from spellbot.models import GuildMember


class GuildMemberFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = GuildMember
        sqlalchemy_session_persistence = "flush"
