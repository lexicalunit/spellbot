import pytest

from spellbot.cogs.leave import LeaveGameCog
from spellbot.interactions import leave_interaction
from spellbot.models import Channel, Guild
from tests.mixins import InteractionContextMixin
from tests.mocks import ctx_game, ctx_user, mock_operations


@pytest.mark.asyncio
class TestCogLeaveGame(InteractionContextMixin):
    async def test_leave(self, guild: Guild, channel: Channel):
        game = ctx_game(self.ctx, guild, channel)
        ctx_user(self.ctx, game=game)

        with mock_operations(leave_interaction):
            leave_interaction.safe_fetch_text_channel.return_value = self.ctx.channel
            leave_interaction.safe_fetch_message.return_value = self.ctx.message

            cog = LeaveGameCog(self.bot)
            await cog.leave.func(cog, self.ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                self.ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )
            leave_interaction.safe_update_embed.assert_called_once()
            safe_update_embed_call = leave_interaction.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": self.settings.EMBED_COLOR,
                "description": (
                    "_A SpellTable link will be created when all players have joined._\n"
                    "\n"
                    f"{guild.motd}\n\n{channel.motd}"
                ),
                "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Waiting for 4 more players to join...**",
                "type": "rich",
            }

    async def test_leave_when_no_message_xid(self, guild: Guild, channel: Channel):
        game = ctx_game(self.ctx, guild, channel, message_xid=None)
        ctx_user(self.ctx, game=game)

        with mock_operations(leave_interaction):
            leave_interaction.safe_fetch_text_channel.return_value = self.ctx.channel
            leave_interaction.safe_fetch_message.return_value = self.ctx.message

            cog = LeaveGameCog(self.bot)
            await cog.leave.func(cog, self.ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                self.ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )

    async def test_leave_when_not_in_game(self):
        with mock_operations(leave_interaction):
            cog = LeaveGameCog(self.bot)
            await cog.leave.func(cog, self.ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                self.ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )

    async def test_leave_when_no_channel(self, guild: Guild, channel: Channel):
        game = ctx_game(self.ctx, guild, channel)
        ctx_user(self.ctx, game=game)

        with mock_operations(leave_interaction):
            leave_interaction.safe_fetch_text_channel.return_value = None

            cog = LeaveGameCog(self.bot)
            await cog.leave.func(cog, self.ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                self.ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )

    async def test_leave_when_no_message(self, guild: Guild, channel: Channel):
        game = ctx_game(self.ctx, guild, channel)
        ctx_user(self.ctx, game=game)

        with mock_operations(leave_interaction):
            leave_interaction.safe_fetch_text_channel.return_value = self.ctx.channel
            leave_interaction.safe_fetch_message.return_value = None

            cog = LeaveGameCog(self.bot)
            await cog.leave.func(cog, self.ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                self.ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )
