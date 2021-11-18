from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord_slash.model import ButtonStyle, ComponentType
from pygicord import Config

from spellbot.cogs.admin import AdminCog
from spellbot.database import DatabaseSession
from spellbot.interactions import admin_interaction, watch_interaction
from spellbot.models import Channel, Game, Guild, GuildAward, Verify, Watch
from tests.mixins import ComponentContextMixin, InteractionContextMixin


@pytest.mark.asyncio
class TestCogAdminSetup(InteractionContextMixin):
    async def test_setup(self):
        assert self.ctx.guild
        cog = AdminCog(self.bot)
        await cog.setup.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["components"] == [
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
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
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
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Setup for {self.ctx.guild.name}",
            "type": "rich",
        }


@pytest.mark.asyncio
class TestCogAdminSetupButtons(ComponentContextMixin):
    async def test_refresh_setup(self):
        assert self.ctx.guild
        cog = AdminCog(self.bot)
        await cog.refresh_setup.func(cog, self.ctx)
        self.ctx.edit_origin.assert_called_once()
        assert self.ctx.edit_origin.call_args_list[0].kwargs["components"] == [
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
        assert self.ctx.edit_origin.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
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
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Setup for {self.ctx.guild.name}",
            "type": "rich",
        }

    async def test_toggle_show_links(self):
        cog = AdminCog(self.bot)
        await cog.toggle_show_links.func(cog, self.ctx)
        self.ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.show_links != Guild.show_links.default.arg  # type: ignore

    async def test_toggle_show_points(self):
        cog = AdminCog(self.bot)
        await cog.toggle_show_points.func(cog, self.ctx)
        self.ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.show_points != Guild.show_points.default.arg  # type: ignore

    async def test_toggle_voice_create(self):
        cog = AdminCog(self.bot)
        await cog.toggle_voice_create.func(cog, self.ctx)
        self.ctx.edit_origin.assert_called_once()
        guild = DatabaseSession.query(Guild).one()
        assert guild.voice_create != Guild.voice_create.default.arg  # type: ignore

    async def test_motd(self):
        cog = AdminCog(self.bot)
        await cog.motd.func(cog, self.ctx, "this is a test")
        self.ctx.send.assert_called_once_with(
            "Message of the day updated.",
            hidden=True,
        )
        guild = DatabaseSession.query(Guild).one()
        assert guild.motd == "this is a test"

        await cog.motd.func(cog, self.ctx)
        DatabaseSession.expire_all()
        guild = DatabaseSession.query(Guild).one()
        assert guild.motd == ""


@pytest.mark.asyncio
class TestCogAdminInfo(InteractionContextMixin):
    async def test_happy_path(self, game: Game):
        cog = AdminCog(self.bot)
        await cog.info.func(cog, self.ctx, f"SB#{game.id}")
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n\n"
                f"{game.guild.motd}\n\n{game.channel.motd}"
            ),
            "fields": [
                {"inline": True, "name": "Format", "value": "Commander"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": self.settings.THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    async def test_non_numeric_game_id(self):
        cog = AdminCog(self.bot)
        await cog.info.func(cog, self.ctx, "bogus")
        self.ctx.send.assert_awaited_once_with(
            "There is no game with that ID.",
            hidden=True,
        )

    async def test_non_existant_game_id(self):
        cog = AdminCog(self.bot)
        await cog.info.func(cog, self.ctx, "1")
        self.ctx.send.assert_awaited_once_with(
            "There is no game with that ID.",
            hidden=True,
        )


@pytest.mark.asyncio
class TestCogAdminWatches(InteractionContextMixin):
    async def test_watch_and_unwatch(self):
        assert self.ctx.guild
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = AdminCog(self.bot)

        await cog.watch.func(cog, self.ctx, target, "note")
        self.ctx.send.assert_called_once_with(f"Watching <@{target.id}>.", hidden=True)

        watch = DatabaseSession.query(Watch).one()
        assert watch.to_dict() == {
            "guild_xid": self.ctx.guild_id,
            "user_xid": target.id,
            "note": "note",
        }

        self.ctx.send = AsyncMock()  # reset mock
        await cog.unwatch.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(
            f"No longer watching <@{target.id}>.",
            hidden=True,
        )

        watch = DatabaseSession.query(Watch).one_or_none()
        assert not watch

    async def test_watched_single_page(self):
        guild1 = self.factories.guild.create()
        guild2 = self.factories.guild.create()
        user1 = self.factories.user.create(xid=101)
        user2 = self.factories.user.create(xid=102)
        user3 = self.factories.user.create(xid=103)
        watch1 = self.factories.watch.create(guild_xid=guild1.xid, user_xid=user1.xid)
        watch2 = self.factories.watch.create(guild_xid=guild1.xid, user_xid=user2.xid)
        self.factories.watch.create(guild_xid=guild2.xid, user_xid=user3.xid)

        self.ctx.guild_id = guild1.xid
        cog = AdminCog(self.bot)
        await cog.watched.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                f"• <@{user1.xid}> — {watch1.note}\n"
                f"• <@{user2.xid}> — {watch2.note}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
        }

    async def test_watched_multiple_pages(self, monkeypatch):
        guild1 = self.factories.guild.create()
        users = [
            self.factories.user.create(xid=101),
            self.factories.user.create(xid=102),
            self.factories.user.create(xid=103),
            self.factories.user.create(xid=104),
            self.factories.user.create(xid=105),
        ]
        watches = [
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[0].xid,
                note="ab " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[1].xid,
                note="cd " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[2].xid,
                note="ef " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[3].xid,
                note="gh " * 333,
            ),
            self.factories.watch.create(
                guild_xid=guild1.xid,
                user_xid=users[4].xid,
                note="ij " * 333,
            ),
        ]

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        self.ctx.guild_id = guild1.xid
        cog = AdminCog(self.bot)
        await cog.watched.func(cog, self.ctx)
        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                f"• <@{users[0].xid}> — {watches[0].note}\n"
                f"• <@{users[1].xid}> — {watches[1].note}\n"
                f"• <@{users[2].xid}> — {watches[2].note}\n"
                f"• <@{users[3].xid}> — {watches[3].note}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 1 of 2"},
        }
        assert pages[1].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (f"• <@{users[4].xid}> — {watches[4].note}\n"),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": "List of watched players on this server",
            "type": "rich",
            "footer": {"text": "page 2 of 2"},
        }
        paginator_mock.start.assert_called_once_with(self.ctx)

    async def test_watched_pagination_start_error(self, monkeypatch, caplog):
        guild1 = self.factories.guild.create()
        user1 = self.factories.user.create(xid=101)
        user2 = self.factories.user.create(xid=102)
        user3 = self.factories.user.create(xid=103)
        user4 = self.factories.user.create(xid=104)
        user5 = self.factories.user.create(xid=105)
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user1.xid,
            note="ab " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user2.xid,
            note="cd " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user3.xid,
            note="ef " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user4.xid,
            note="gh " * 333,
        )
        self.factories.watch.create(
            guild_xid=guild1.xid,
            user_xid=user5.xid,
            note="ij " * 333,
        )

        paginator_mock = MagicMock()
        error = RuntimeError("start-error")
        paginator_mock.start = AsyncMock(side_effect=error)
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(watch_interaction, "Paginator", Paginator_mock)

        self.ctx.guild_id = guild1.xid
        cog = AdminCog(self.bot)
        await cog.watched.func(cog, self.ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text


@pytest.mark.asyncio
class TestCogAdminChannels(InteractionContextMixin):
    async def test_default_seats(self):
        cog = AdminCog(self.bot)
        seats = Channel.default_seats.default.arg - 1  # type: ignore
        await cog.default_seats.func(cog, self.ctx, seats)
        self.ctx.send.assert_called_once_with(
            f"Default seats set to {seats} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_seats == seats

    async def test_auto_verify(self):
        cog = AdminCog(self.bot)
        default_value = Channel.auto_verify.default.arg  # type: ignore
        await cog.auto_verify.func(cog, self.ctx, not default_value)
        self.ctx.send.assert_called_once_with(
            f"Auto verification set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.auto_verify != default_value

    async def test_verified_only(self):
        cog = AdminCog(self.bot)
        default_value = Channel.verified_only.default.arg  # type: ignore
        await cog.verified_only.func(cog, self.ctx, not default_value)
        self.ctx.send.assert_called_once_with(
            f"Verified only set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.verified_only != default_value

    async def test_unverified_only(self):
        cog = AdminCog(self.bot)
        default_value = Channel.unverified_only.default.arg  # type: ignore
        await cog.unverified_only.func(cog, self.ctx, not default_value)
        self.ctx.send.assert_called_once_with(
            f"Unverified only set to {not default_value} for this channel.",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.unverified_only != default_value

    async def test_channel_motd(self):
        cog = AdminCog(self.bot)
        motd = "this is a channel message of the day"
        await cog.channel_motd.func(cog, self.ctx, motd)
        self.ctx.send.assert_called_once_with(
            f"Message of the day for this channel has been set to: {motd}",
            hidden=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.motd == motd

        await cog.channel_motd.func(cog, self.ctx)
        DatabaseSession.expire_all()
        channel = DatabaseSession.query(Channel).one()
        assert channel.motd == ""

    async def test_channels(self):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        channel1 = self.factories.channel.create(guild=guild, auto_verify=True)
        channel2 = self.factories.channel.create(guild=guild, unverified_only=True)
        channel3 = self.factories.channel.create(guild=guild, verified_only=True)
        channel4 = self.factories.channel.create(guild=guild, default_seats=2)
        cog = AdminCog(self.bot)
        await cog.channels.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                f"• <#{channel1.xid}> — `auto_verify`\n"
                f"• <#{channel2.xid}> — `unverified_only`\n"
                f"• <#{channel3.xid}> — `verified_only`\n"
                f"• <#{channel4.xid}> — `default_seats=2`\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"Configuration for channels in {self.ctx.guild.name}",
            "type": "rich",
        }

    async def test_channels_when_no_non_default_channels(self):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        self.factories.channel.create(guild=guild)
        cog = AdminCog(self.bot)
        await cog.channels.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                "**All channels on this server have a default configuration.**\n\n"
                "Use may use channel specific `/set` commands within a channel"
                " to change that channel's configuration."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"Configuration for channels in {self.ctx.guild.name}",
            "type": "rich",
        }

    async def test_channels_with_pagination(self, monkeypatch):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        self.factories.channel.create_batch(
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
        monkeypatch.setattr(admin_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(self.bot)
        await cog.channels.func(cog, self.ctx)

        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict()["footer"] == {"text": "page 1 of 2"}
        assert pages[1].to_dict()["footer"] == {"text": "page 2 of 2"}

    async def test_awards_with_pagination_start_error(self, monkeypatch, caplog):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        self.factories.channel.create_batch(
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
        monkeypatch.setattr(admin_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(self.bot)
        await cog.channels.func(cog, self.ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text


@pytest.mark.asyncio
class TestCogAdminAwards(InteractionContextMixin):
    async def test_awards(self):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        award1 = self.factories.guild_award.create(
            guild=guild,
            count=10,
            role="role1",
            message="msg1",
        )
        award2 = self.factories.guild_award.create(
            guild=guild,
            count=20,
            role="role2",
            message="msg2",
        )
        award3 = self.factories.guild_award.create(
            guild=guild,
            count=30,
            role="role3",
            message="msg3",
        )
        cog = AdminCog(self.bot)
        await cog.awards.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                f"• **ID {award1.id}** — _after {award1.count}"
                f" games_ — `@{award1.role}` — {award1.message}\n"
                f"• **ID {award2.id}** — _after {award2.count}"
                f" games_ — `@{award2.role}` — {award2.message}\n"
                f"• **ID {award3.id}** — _after {award3.count}"
                f" games_ — `@{award3.role}` — {award3.message}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Player Awards for {self.ctx.guild.name}",
            "type": "rich",
        }

    async def test_awards_when_no_awards(self):
        assert self.ctx.guild
        cog = AdminCog(self.bot)
        await cog.awards.func(cog, self.ctx)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                "**There are no awards configured on this server.**\n\n"
                "To add awards use the `/award add` command."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Player Awards for {self.ctx.guild.name}",
            "type": "rich",
        }

    async def test_awards_with_pagination(self, monkeypatch):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        self.factories.guild_award.create_batch(
            40,
            guild=guild,
            count=10,
            role="this-is-a-role-name",
            message="mm" * 50,
        )

        paginator_mock = MagicMock()
        paginator_mock.start = AsyncMock()
        Paginator_mock = MagicMock(return_value=paginator_mock)
        monkeypatch.setattr(admin_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(self.bot)
        await cog.awards.func(cog, self.ctx)

        Paginator_mock.assert_called_once()
        assert Paginator_mock.call_args_list[0].kwargs["config"] is Config.MINIMAL
        pages = Paginator_mock.call_args_list[0].kwargs["pages"]
        assert len(pages) == 2
        assert pages[0].to_dict()["footer"] == {"text": "page 1 of 2"}
        assert pages[1].to_dict()["footer"] == {"text": "page 2 of 2"}

    async def test_awards_with_pagination_start_error(self, monkeypatch, caplog):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        self.factories.guild_award.create_batch(
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
        monkeypatch.setattr(admin_interaction, "Paginator", Paginator_mock)

        cog = AdminCog(self.bot)
        await cog.awards.func(cog, self.ctx)

        assert "warning: discord: pagination error: start-error" in caplog.text

    async def test_award_delete(self):
        assert self.ctx.guild
        guild = self.factories.guild.create(
            xid=self.ctx.guild_id,
            name=self.ctx.guild.name,
        )
        awards = self.factories.guild_award.create_batch(2, guild=guild)

        cog = AdminCog(self.bot)
        await cog.award_delete.func(cog, self.ctx, awards[0].id)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "author": {"name": "Award deleted!"},
            "color": self.settings.EMBED_COLOR,
            "description": "You can view all awards with the `/set awards` command.",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
        }
        assert self.ctx.send.call_args_list[0].kwargs["hidden"]
        assert DatabaseSession.query(GuildAward).count() == 1

    async def test_award_add(self):
        cog = AdminCog(self.bot)
        await cog.award_add.func(cog, self.ctx, 10, "role", "message", repeating=True)
        self.ctx.send.assert_called_once()
        assert self.ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "author": {"name": "Award added!"},
            "color": self.settings.EMBED_COLOR,
            "description": (
                "• _every 10 games_ — `@role` — message\n\n"
                "You can view all awards with the `/set awards` command."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
        }
        assert self.ctx.send.call_args_list[0].kwargs["hidden"]
        award = DatabaseSession.query(GuildAward).one()
        assert award.count == 10
        assert award.role == "role"
        assert award.message == "message"
        assert award.repeating

    async def test_award_add_zero_count(self):
        cog = AdminCog(self.bot)
        await cog.award_add.func(cog, self.ctx, 0, "role", "message")
        self.ctx.send.assert_called_once_with(
            "You can't create an award for zero games played.",
            hidden=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 0

    async def test_award_add_dupe(self):
        cog = AdminCog(self.bot)
        await cog.award_add.func(cog, self.ctx, 10, "role", "message")

        self.ctx.send = AsyncMock()  # reset mock
        await cog.award_add.func(cog, self.ctx, 10, "role", "message")
        self.ctx.send.assert_called_once_with(
            "There's already an award for players who reach that many games.",
            hidden=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 1


@pytest.mark.asyncio
class TestCogAdminVerifies(InteractionContextMixin):
    async def test_verify_and_unverify(self):
        target = MagicMock(spec=discord.Member)
        target.id = 1002
        target.display_name = "user"
        cog = AdminCog(self.bot)

        await cog.verify.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(f"Verified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert found.guild_xid == self.ctx.guild_id
        assert found.user_xid == target.id
        assert found.verified

        self.ctx.send = AsyncMock()  # reset mock
        await cog.unverify.func(cog, self.ctx, target)
        self.ctx.send.assert_called_once_with(f"Unverified <@{target.id}>.", hidden=True)

        found = DatabaseSession.query(Verify).filter(Verify.user_xid == target.id).one()
        assert not found.verified
