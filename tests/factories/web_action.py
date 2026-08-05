from __future__ import annotations

import factory

from spellbot.models import WebAction


class WebActionFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = WebAction
        sqlalchemy_session_persistence = "flush"
