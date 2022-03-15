from __future__ import annotations

import pytest

from spellbot.actions import config_action
from spellbot.client import SpellBot
from spellbot.cogs import ConfigCog
from spellbot.database import DatabaseSession
from spellbot.models import Config, User
from tests.mixins import InteractionMixin
from tests.mocks import mock_operations


@pytest.fixture
def cog(bot: SpellBot) -> ConfigCog:
    return ConfigCog(bot)


@pytest.mark.asyncio
class TestCogConfig(InteractionMixin):
    async def test_power_level(self, cog: ConfigCog):
        await self.run(cog.power, level=10)

        config = DatabaseSession.query(Config).one()
        assert self.interaction.guild is not None
        assert config.guild_xid == self.interaction.guild.id
        assert config.user_xid == self.interaction.user.id
        assert config.power_level == 10


@pytest.mark.asyncio
class TestCogConfigPowerLevelWhenUserWaiting(InteractionMixin):
    async def test_happy_path(self, cog: ConfigCog, player: User):
        with mock_operations(config_action):
            config_action.safe_fetch_text_channel.return_value = self.interaction.channel
            config_action.safe_get_partial_message.return_value = self.interaction.message

            await self.run(cog.power, level=10)

            update_embed_call = config_action.safe_update_embed
            update_embed_call.assert_called_once()
            assert update_embed_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{player.game.guild.motd}\n"
                    "\n"
                    f"{player.game.channel.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"<@{player.xid}> (power level: 10)",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{player.game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
            }

    async def test_when_channel_not_found(self, cog: ConfigCog, player: User):
        with mock_operations(config_action):
            config_action.safe_fetch_text_channel.return_value = None

            await self.run(cog.power, level=10)

            config_action.safe_update_embed.assert_not_called()

    async def test_when_message_not_found(self, cog: ConfigCog, player: User):
        with mock_operations(config_action):
            config_action.safe_fetch_text_channel.return_value = self.interaction.channel
            config_action.safe_get_partial_message.return_value = None

            await self.run(cog.power, level=10)

            config_action.safe_update_embed.assert_not_called()
