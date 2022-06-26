from __future__ import annotations

import factory

from spellbot.models import Verify


class VerifyFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Verify
        sqlalchemy_session_persistence = "flush"
