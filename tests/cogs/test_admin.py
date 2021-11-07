from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord_slash.context import ComponentContext, InteractionContext
from discord_slash.model import ButtonStyle, ComponentType
from pygicord import Config

from spellbot.client import SpellBot
from spellbot.cogs.admin import AdminCog
from spellbot.database import DatabaseSession
from spellbot.interactions import config_interaction, watch_interaction
from spellbot.models import Channel, Game, Guild, GuildAward, Verify, Watch
from spellbot.settings import Settings
from tests.fixtures import Factories


@pytest.mark.asyncio
class TestCogAdmin:
    async def test_setup(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
    ):
        assert ctx.guild
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.setup.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["components"] == [
            {
                "components": (
                    {
                        "custom_id": "toggle_show_links",
                        "label": "Toggle Public Links",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                    {
                        "custom_id": "toggle_show_points",
                        "label": "Toggle Show Points",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                    {
                        "custom_id": "toggle_voice_create",
                        "label": "Toggle Create Voice Channels",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                ),
                "type": ComponentType.actionrow,
            },
            {
                "components": (
                    {
                        "custom_id": "refresh_setup",
                        "label": "Refresh",
                        "style": ButtonStyle.secondary,
                        "type": ComponentType.button,
                    },
                ),
                "type": ComponentType.actionrow,
            },
        ]
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "These are the current settings for SpellBot on this server. "
                "Please use the buttons below, as well as the `/set` commands, "
                "to setup SpellBot as you wish.\n\n"
                "You may also view Awards configuration using the `/awards` "
                "command and Channels configuration using the `/channels` command."
            ),
            "fields": [
                {"inline": False, "name": "MOTD", "value": "None"},
                {"inline": True, "name": "Public Links", "value": "❌ Off"},
                {"inline": True, "name": "Show Points on Games", "value": "❌ Off"},
                {"inline": True, "name": "Create Voice Channels", "value": "❌ Off"},
            ],
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"SpellBot Setup for {ctx.guild.name}",
            "type": "rich",
        }

    async def test_refresh_setup(
        self,
        bot: SpellBot,
        ctx: ComponentContext,
        settings: Settings,
    ):
        assert ctx.guild
        ctx.origin_message_id = 12345
        ctx.edit_origin = AsyncMock()
        cog = AdminCog(bot)
        await cog.refresh_setup.func(cog, ctx)
        ctx.edit_origin.assert_called_once()
        assert ctx.edit_origin.call_args_list[0].kwargs["components"] == [
            {
                "components": (
                    {
                        "custom_id": "toggle_show_links",
                        "label": "Toggle Public Links",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                    {
                        "custom_id": "toggle_show_points",
                        "label": "Toggle Show Points",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                    {
                        "custom_id": "toggle_voice_create",
                        "label": "Toggle Create Voice Channels",
                        "style": ButtonStyle.primary,
                        "type": ComponentType.button,
                    },
                ),
                "type": ComponentType.actionrow,
            },
            {
                "components": (
                    {
                        "custom_id": "refresh_setup",
                        "label": "Refresh",
                        "style": ButtonStyle.secondary,
                        "type": ComponentType.button,
                    },
                ),
                "type": ComponentType.actionrow,
            },
        ]
        assert ctx.edit_origin.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "These are the current settings for SpellBot on this server. "
                "Please use the buttons below, as well as the `/set` commands, "
                "to setup SpellBot as you wish.\n\n"
                "You may also view Awards configuration using the `/awards` "
                "command and Channels configuration using the `/channels` command."
            ),
            "fields": [
                {"inline": False, "name": "MOTD", "value": "None"},
                {"inline": True, "name": "Public Links", "value": "❌ Off"},
                {"inline": True, "name": "Show Points on Games", "value": "❌ Off"},
                {"inline": True, "name": "Create Voice Channels", "value": "❌ Off"},
            ],
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"SpellBot Setup for {ctx.guild.name}",
            "type": "rich",
        }

    async def test_toggle_show_links(self, bot: SpellBot, origin_ctx: ComponentContext):
        cog = AdminCog(bot)
        await cog.toggle_show_links.func(cog, origin_ctx)
        origin_ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.show_links != Guild.show_links.default.arg  # type: ignore

    async def test_toggle_show_points(self, bot: SpellBot, origin_ctx: ComponentContext):
        cog = AdminCog(bot)
        await cog.toggle_show_points.func(cog, origin_ctx)
        origin_ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.show_points != Guild.show_points.default.arg  # type: ignore

    async def test_toggle_voice_create(self, bot: SpellBot, origin_ctx: ComponentContext):
        cog = AdminCog(bot)
        await cog.toggle_voice_create.func(cog, origin_ctx)
        origin_ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.voice_create != Guild.voice_create.default.arg  # type: ignore

    async def test_motd(self, bot: SpellBot, ctx: ComponentContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.motd.func(cog, ctx, "this is a test")
        ctx.send.assert_called_once_with("Message of the day updated.", hidden=True)
        guild = DatabaseSession.query(Guild).one()
        assert guild.motd == "this is a test"


@pytest.mark.asyncio
class TestCogAdminInfo:
    async def test_happy_path(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        game: Game,
    ):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.info.func(cog, ctx, f"SB#{game.id}")
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n\n"
                f"{game.guild.motd}"
            ),
            "fields": [
                {"inline": True, "name": "Format", "value": "Commander"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    async def test_non_numeric_game_id(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.info.func(cog, ctx, "bogus")
        ctx.send.assert_awaited_once_with("There is no game with that ID.", hidden=True)

    async def test_non_existant_game_id(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.info.func(cog, ctx, "1")
        ctx.send.assert_awaited_once_with("There is no game with that ID.", hidden=True)


@pytest.mark.asyncio
class TestCogAdminWatches:
    async def test_watch_and_unwatch(self, bot: SpellBot, ctx: InteractionContext):
        assert ctx.guild
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = AdminCog(bot)

        ctx.send = AsyncMock()
        await cog.watch.func(cog, ctx, target, "note")
        ctx.send.assert_called_once_with(f"Watching <@{target.id}>.", hidden=True)

        watch = DatabaseSession.query(Watch).one()
        assert watch.to_dict() == {
            "guild_xid": ctx.guild_id,
            "user_xid": target.id,
            "note": "note",
        }

        ctx.send = AsyncMock()
        await cog.unwatch.func(cog, ctx, target)
        ctx.send.assert_called_once_with(
            f"No longer watching <@{target.id}>.",
            hidden=True,
        )

        watch = DatabaseSession.query(Watch).one_or_none()
        assert not watch

    async def test_watched_single_page(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        guild1 = factories.guild.create()
        guild2 = factories.guild.create()
        user1 = factories.user.create(xid=101)
        user2 = factories.user.create(xid=102)
        user3 = factories.user.create(xid=103)
        watch1 = factories.watch.create(guild_xid=guild1.xid, user_xid=user1.xid)
        watch2 = factories.watch.create(guild_xid=guild1.xid, user_xid=user2.xid)
        factories.watch.create(guild_xid=guild2.xid, user_xid=user3.xid)

        ctx.send = AsyncMock()
        ctx.guild_id = guild1.xid
        cog = AdminCog(bot)
        await cog.watched.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                f"• <@{user1.xid}> — {watch1.note}\n"
                f"• <@{user2.xid}> — {watch2.note}\n"
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
        }

    async def test_watched_multiple_pages(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
        monkeypatch,
    ):
        guild1 = factories.guild.create()
        user1 = factories.user.create(xid=101)
        user2 = factories.user.create(xid=102)
        user3 = factories.user.create(xid=103)
        user4 = factories.user.create(xid=104)
        user5 = factories.user.create(xid=105)
        watch1 = factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user1.xid,
            note="ab " * 333,
        )
        watch2 = factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user2.xid,
            note="cd " * 333,
        )
        watch3 = factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user3.xid,
            note="ef " * 333,
        )
        watch4 = factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user4.xid,
            note="gh " * 333,
        )
        watch5 = factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user5.xid,
            note="ij " * 333,
        )

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        ctx.guild_id = guild1.xid
        cog = AdminCog(bot)
        await cog.watched.func(cog, ctx)
        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                f"• <@{user1.xid}> — {watch1.note}\n"
                f"• <@{user2.xid}> — {watch2.note}\n"
                f"• <@{user3.xid}> — {watch3.note}\n"
                f"• <@{user4.xid}> — {watch4.note}\n"
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 1 of 2"},
        }
        assert pages[1].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (f"• <@{user5.xid}> — {watch5.note}\n"),
            "thumbnail": {"url": settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 2 of 2"},
        }
        paginator_mock.start.assert_called_once_with(ctx)

    async def test_watched_pagination_start_error(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
        caplog,
    ):
        guild1 = factories.guild.create()
        user1 = factories.user.create(xid=101)
        user2 = factories.user.create(xid=102)
        user3 = factories.user.create(xid=103)
        user4 = factories.user.create(xid=104)
        user5 = factories.user.create(xid=105)
        factories.watch.create(guild_xid=guild1.xid, user_xid=user1.xid, note="ab " * 333)
        factories.watch.create(guild_xid=guild1.xid, user_xid=user2.xid, note="cd " * 333)
        factories.watch.create(guild_xid=guild1.xid, user_xid=user3.xid, note="ef " * 333)
        factories.watch.create(guild_xid=guild1.xid, user_xid=user4.xid, note="gh " * 333)
        factories.watch.create(guild_xid=guild1.xid, user_xid=user5.xid, note="ij " * 333)

        paginator_mock = MagicMock()
        error = RuntimeError("start-error")
        paginator_mock.start = AsyncMock(side_effect=error)
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        ctx.guild_id = guild1.xid
        cog = AdminCog(bot)
        await cog.watched.func(cog, ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text


@pytest.mark.asyncio
class TestCogAdminChannels:
    async def test_default_seats(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        seats = Channel.default_seats.default.arg - 1  # type: ignore
        await cog.default_seats.func(cog, ctx, seats)
        ctx.send.assert_called_once_with(
            f"Default seats set to {seats} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_seats == seats

    async def test_auto_verify(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        default_value = Channel.auto_verify.default.arg  # type: ignore
        await cog.auto_verify.func(cog, ctx, not default_value)
        ctx.send.assert_called_once_with(
            f"Auto verification set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.auto_verify != default_value

    async def test_verified_only(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        default_value = Channel.verified_only.default.arg  # type: ignore
        await cog.verified_only.func(cog, ctx, not default_value)
        ctx.send.assert_called_once_with(
            f"Verified only set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.verified_only != default_value

    async def test_unverified_only(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        default_value = Channel.unverified_only.default.arg  # type: ignore
        await cog.unverified_only.func(cog, ctx, not default_value)
        ctx.send.assert_called_once_with(
            f"Unverified only set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.unverified_only != default_value

    async def test_channels(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        channel1 = factories.channel.create(guild=guild, auto_verify=True)
        channel2 = factories.channel.create(guild=guild, unverified_only=True)
        channel3 = factories.channel.create(guild=guild, verified_only=True)
        channel4 = factories.channel.create(guild=guild, default_seats=2)
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.channels.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                f"• <#{channel1.xid}> — `auto_verify`\n"
                f"• <#{channel2.xid}> — `unverified_only`\n"
                f"• <#{channel3.xid}> — `verified_only`\n"
                f"• <#{channel4.xid}> — `default_seats=2`\n"
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"Configuration for channels in {ctx.guild.name}",
            "type": "rich",
        }

    async def test_channels_when_no_non_default_channels(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        factories.channel.create(guild=guild)
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.channels.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "**All channels on this server have a default configuration.**\n\n"
                "Use may use channel specific `/set` commands within a channel"
                " to change that channel's configuration."
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"Configuration for channels in {ctx.guild.name}",
            "type": "rich",
        }

    async def test_channels_with_pagination(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        factories.channel.create_batch(
            100,
            guild=guild,
            default_seats=2,
            auto_verify=True,
            unverified_only=True,
            verified_only=True,
        )

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(config_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(bot)
        await cog.channels.func(cog, ctx)

        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict()["footer"] == {"text": "page 1 of 2"}
        assert pages[1].to_dict()["footer"] == {"text": "page 2 of 2"}

    async def test_awards_with_pagination_start_error(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
        caplog,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        factories.channel.create_batch(
            100,
            guild=guild,
            default_seats=2,
            auto_verify=True,
            unverified_only=True,
            verified_only=True,
        )

        paginator_mock = MagicMock()
        error = RuntimeError("start-error")
        paginator_mock.start = AsyncMock(side_effect=error)
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(config_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(bot)
        await cog.channels.func(cog, ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text


@pytest.mark.asyncio
class TestCogAdminAwards:
    async def test_awards(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        award1 = factories.guild_award.create(
            guild=guild,
            count=10,
            role="role1",
            message="msg1",
        )
        award2 = factories.guild_award.create(
            guild=guild,
            count=20,
            role="role2",
            message="msg2",
        )
        award3 = factories.guild_award.create(
            guild=guild,
            count=30,
            role="role3",
            message="msg3",
        )
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.awards.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                f"• **ID {award1.id}** — _after {award1.count}"
                f" games_ — `@{award1.role}` — {award1.message}\n"
                f"• **ID {award2.id}** — _after {award2.count}"
                f" games_ — `@{award2.role}` — {award2.message}\n"
                f"• **ID {award3.id}** — _after {award3.count}"
                f" games_ — `@{award3.role}` — {award3.message}\n"
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"SpellBot Player Awards for {ctx.guild.name}",
            "type": "rich",
        }

    async def test_awards_when_no_awards(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
    ):
        assert ctx.guild
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.awards.func(cog, ctx)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "**There are no awards configured on this server.**\n\n"
                "To add awards use the `/award add` command."
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "title": f"SpellBot Player Awards for {ctx.guild.name}",
            "type": "rich",
        }

    async def test_awards_with_pagination(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        factories.guild_award.create_batch(
            40,
            guild=guild,
            count=10,
            role="this-is-a-role-name",
            message="mm" * 50,
        )

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(config_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(bot)
        await cog.awards.func(cog, ctx)

        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict()["footer"] == {"text": "page 1 of 2"}
        assert pages[1].to_dict()["footer"] == {"text": "page 2 of 2"}

    async def test_awards_with_pagination_start_error(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
        caplog,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        factories.guild_award.create_batch(
            40,
            guild=guild,
            count=10,
            role="this-is-a-role-name",
            message="mm" * 50,
        )

        paginator_mock = MagicMock()
        error = RuntimeError("start-error")
        paginator_mock.start = AsyncMock(side_effect=error)
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(config_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(bot)
        await cog.awards.func(cog, ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text

    async def test_award_delete(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        assert ctx.guild
        guild = factories.guild.create(xid=ctx.guild_id, name=ctx.guild.name)
        awards = factories.guild_award.create_batch(2, guild=guild)

        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.award_delete.func(cog, ctx, awards[0].id)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "author": {"name": "Award deleted!"},
            "color": settings.EMBED_COLOR,
            "description": "You can view all awards with the `/set awards` command.",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }
        assert ctx.send.call_args_list[0].kwargs["hidden"]
        assert DatabaseSession.query(GuildAward).count() == 1

    async def test_award_add(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
    ):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.award_add.func(cog, ctx, 10, "role", "message", repeating=True)
        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "author": {"name": "Award added!"},
            "color": settings.EMBED_COLOR,
            "description": (
                "• _every 10 games_ — `@role` — message\n\n"
                "You can view all awards with the `/set awards` command."
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }
        assert ctx.send.call_args_list[0].kwargs["hidden"]
        award = DatabaseSession.query(GuildAward).one()
        assert award.count == 10
        assert award.role == "role"
        assert award.message == "message"
        assert award.repeating

    async def test_award_add_zero_count(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.award_add.func(cog, ctx, 0, "role", "message")
        ctx.send.assert_called_once_with(
            "You can't create an award for zero games played.",
            hidden=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 0

    async def test_award_add_dupe(self, bot: SpellBot, ctx: InteractionContext):
        ctx.send = AsyncMock()
        cog = AdminCog(bot)
        await cog.award_add.func(cog, ctx, 10, "role", "message")

        ctx.send = AsyncMock()
        await cog.award_add.func(cog, ctx, 10, "role", "message")
        ctx.send.assert_called_once_with(
            "There's already an award for players who reach that many games.",
            hidden=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 1


@pytest.mark.asyncio
class TestCogAdminVerifies:
    async def test_verify_and_unverify(self, bot: SpellBot, ctx: InteractionContext):
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = AdminCog(bot)

        ctx.send = AsyncMock()
        await cog.verify.func(cog, ctx, target)
        ctx.send.assert_called_once_with(f"Verified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == ctx.guild_id
        assert found.user_xid == target.id
        assert found.verified

        ctx.send = AsyncMock()
        await cog.unverify.func(cog, ctx, target)
        ctx.send.assert_called_once_with(f"Unverified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).one()
        assert not found.verified
