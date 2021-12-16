import pytest

from spellbot.cogs.config_cog import ConfigCog
from spellbot.database import DatabaseSession
from spellbot.interactions import config_interaction
from spellbot.models import Config
from tests.mixins import InteractionContextMixin
from tests.mocks import ctx_channel, ctx_game, ctx_guild, ctx_user, mock_operations


@pytest.mark.asyncio
class TestCogConfig(InteractionContextMixin):
    async def test_power_level(self):
        guild = ctx_guild(self.ctx)
        user = ctx_user(self.ctx)

        cog = ConfigCog(self.bot)
        await cog.power.func(cog, self.ctx, level=10)

        config = DatabaseSession.query(Config).one()
        assert config.guild_xid == guild.xid
        assert config.user_xid == user.xid
        assert config.power_level == 10


@pytest.mark.asyncio
class TestCogConfigPowerLevelWhenUserWaiting(InteractionContextMixin):
    async def test_happy_path(self):
        guild = ctx_guild(self.ctx, motd=None)
        channel = ctx_channel(self.ctx, guild=guild, motd=None)
        game = ctx_game(self.ctx, guild=guild, channel=channel)
        user = ctx_user(self.ctx, game=game)

        with mock_operations(config_interaction):
            config_interaction.safe_fetch_text_channel.return_value = self.ctx.channel
            config_interaction.safe_get_partial_message.return_value = self.ctx.message

            cog = ConfigCog(self.bot)
            await cog.power.func(cog, self.ctx, level=10)

            update_embed_call = config_interaction.safe_update_embed
            update_embed_call.assert_called_once()
            assert update_embed_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"<@{user.xid}> (power level: 10)",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
            }

    async def test_when_channel_not_found(self):
        guild = ctx_guild(self.ctx, motd=None)
        channel = ctx_channel(self.ctx, guild=guild, motd=None)
        game = ctx_game(self.ctx, guild=guild, channel=channel)
        ctx_user(self.ctx, game=game)

        with mock_operations(config_interaction):
            config_interaction.safe_fetch_text_channel.return_value = None

            cog = ConfigCog(self.bot)
            await cog.power.func(cog, self.ctx, level=10)

            config_interaction.safe_update_embed.assert_not_called()

    async def test_when_message_not_found(self):
        guild = ctx_guild(self.ctx, motd=None)
        channel = ctx_channel(self.ctx, guild=guild, motd=None)
        game = ctx_game(self.ctx, guild=guild, channel=channel)
        ctx_user(self.ctx, game=game)

        with mock_operations(config_interaction):
            config_interaction.safe_fetch_text_channel.return_value = self.ctx.channel
            config_interaction.safe_get_partial_message.return_value = None

            cog = ConfigCog(self.bot)
            await cog.power.func(cog, self.ctx, level=10)

            config_interaction.safe_update_embed.assert_not_called()
