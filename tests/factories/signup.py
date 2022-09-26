from __future__ import annotations

import factory

from spellbot.models import Signup


class SignupFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Signup
        sqlalchemy_session_persistence = "flush"
