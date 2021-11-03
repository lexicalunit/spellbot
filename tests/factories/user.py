import factory

from spellbot.models.user import User


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 3000 + n)
    name = factory.Faker("name")

    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"
