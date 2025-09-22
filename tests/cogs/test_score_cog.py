from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest
import pytest_asyncio

from spellbot.cogs import ScoreCog
from tests.mixins import InteractionMixin
from tests.mocks import build_channel, build_guild, build_interaction, mock_discord_object

if TYPE_CHECKING:
    from collections.abc import Callable

    import discord
    from freezegun.api import FrozenDateTimeFactory

    from spellbot import SpellBot
    from spellbot.models import Channel, User

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> ScoreCog:
    return ScoreCog(bot)


@pytest.mark.asyncio
class TestCogScore(InteractionMixin):
    async def test_score(self, cog: ScoreCog, user: User, channel: Channel) -> None:
        await self.run(cog.score)

        assert self.last_send_message("embed") == {
            "author": {"name": f"Record of games played on {self.guild.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"<@{user.xid}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{self.guild.xid}/u/{user.xid}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

        game = self.factories.game.create(
            seats=2,
            guild_xid=self.guild.xid,
            channel_xid=channel.xid,
        )
        self.factories.play.create(user_xid=user.xid, game_id=game.id)

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.score)

        assert self.last_send_message("embed") == {
            "author": {"name": f"Record of games played on {self.guild.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"<@{user.xid}> has played 1 game on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{self.guild.xid}/u/{user.xid}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

        game = self.factories.game.create(
            seats=2,
            guild_xid=self.guild.xid,
            channel_xid=channel.xid,
        )
        self.factories.play.create(user_xid=user.xid, game_id=game.id)

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.score)
        assert self.last_send_message("embed") == {
            "author": {"name": f"Record of games played on {self.guild.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"<@{user.xid}> has played 2 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{self.guild.xid}/u/{user.xid}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

        new_guild = build_guild(2)
        new_channel = build_channel(new_guild, 2)
        discord_user = mock_discord_object(user)
        new_interaction = build_interaction(new_guild, new_channel, discord_user)
        await self.run(cog.score, interaction=new_interaction)

        send_message = new_interaction.response.send_message
        send_message.assert_called_once()  # type: ignore
        embed = send_message.call_args.kwargs.get("embed")  # type: ignore
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {new_guild.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"<@{user.xid}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{new_guild.id}/u/{user.xid}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

    async def test_score_for_other_user(self, cog: ScoreCog, add_user: Callable[..., User]) -> None:
        target_user = add_user()
        target_member = cast("discord.Member", mock_discord_object(target_user))
        await self.run(cog.score, user=target_member)

        assert self.last_send_message("embed") == {
            "author": {"name": f"Record of games played on {self.guild.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": f"<@{target_member.id}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{self.guild.xid}/u/{target_member.id}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

    async def test_history(self, cog: ScoreCog, channel: Channel) -> None:
        await self.run(cog.history)

        assert self.last_send_message("embed") == {
            "author": {"name": f"Recent games played in {channel.name}"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": "View [game history on spellbot.io]"
            f"(https://bot.spellbot.io/g/{self.guild.xid}/c/{channel.xid}).",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

    async def test_top(
        self,
        cog: ScoreCog,
        channel: Channel,
        add_user: Callable[..., User],
        freezer: FrozenDateTimeFactory,
    ) -> None:
        now = datetime(2020, 1, 1, tzinfo=UTC)
        freezer.move_to(now)

        user1 = add_user()
        for _ in range(5):
            game = self.factories.game.create(
                guild_xid=self.guild.xid,
                channel_xid=channel.xid,
                started_at=now,
            )
            self.factories.play.create(user_xid=user1.xid, game_id=game.id)

        user2 = add_user()
        for _ in range(10):
            game = self.factories.game.create(
                guild_xid=self.guild.xid,
                channel_xid=channel.xid,
                started_at=now,
            )
            self.factories.play.create(user_xid=user2.xid, game_id=game.id)

        user3 = add_user()
        for _ in range(15):
            game = self.factories.game.create(
                guild_xid=self.guild.xid,
                channel_xid=channel.xid,
                started_at=now,
            )
            self.factories.play.create(user_xid=user3.xid, game_id=game.id)

        user4 = add_user()
        for _ in range(20):
            game = self.factories.game.create(
                guild_xid=self.guild.xid,
                channel_xid=channel.xid,
                started_at=now - timedelta(days=5),
            )
            self.factories.play.create(user_xid=user4.xid, game_id=game.id)

        await self.run(cog.top, monthly=False)
        assert self.last_send_message("embed") == {
            "title": f"Top players in #{channel.name} (all time)",
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "Rank \xa0\xa0\xa0 Games \xa0\xa0\xa0 Player\n"
                f"{1:\xa0>6}\xa0{20:\xa0>20}\xa0\xa0\xa0<@{user4.xid}>\n"
                f"{2:\xa0>6}\xa0{15:\xa0>20}\xa0\xa0\xa0<@{user3.xid}>\n"
                f"{3:\xa0>6}\xa0{10:\xa0>20}\xa0\xa0\xa0<@{user2.xid}>\n"
                f"{4:\xa0>6}\xa0{5:\xa0>20}\xa0\xa0\xa0<@{user1.xid}>\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.top)
        assert self.last_send_message("embed") == {
            "title": f"Top players in #{channel.name} (this month)",
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "Rank \xa0\xa0\xa0 Games \xa0\xa0\xa0 Player\n"
                f"{1:\xa0>6}\xa0{15:\xa0>20}\xa0\xa0\xa0<@{user3.xid}>\n"
                f"{2:\xa0>6}\xa0{10:\xa0>20}\xa0\xa0\xa0<@{user2.xid}>\n"
                f"{3:\xa0>6}\xa0{5:\xa0>20}\xa0\xa0\xa0<@{user1.xid}>\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.top, ago=1)
        assert self.last_send_message("embed") == {
            "title": f"Top players in #{channel.name} (1 months ago)",
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "Rank \xa0\xa0\xa0 Games \xa0\xa0\xa0 Player\n"
                f"{1:\xa0>6}\xa0{20:\xa0>20}\xa0\xa0\xa0<@{user4.xid}>\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }
