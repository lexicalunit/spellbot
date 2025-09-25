from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock

import discord
import pytest
import pytest_asyncio

from spellbot.actions import admin_action
from spellbot.cogs import AdminCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.errors import AdminOnlyError
from spellbot.models import Channel, Game, Guild, GuildAward
from spellbot.views import SetupView
from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_user, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from spellbot.client import SpellBot
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> AdminCog:
    return AdminCog(bot)


@pytest_asyncio.fixture
async def view(bot: SpellBot) -> SetupView:
    return SetupView(bot)


@pytest.mark.asyncio
class TestCogAdminSetup(InteractionMixin):
    async def test_setup(self, cog: AdminCog) -> None:
        await self.run(cog.setup)

        assert self.last_send_message("view") == [
            {
                "components": [
                    {
                        "custom_id": "toggle_show_links",
                        "label": "Toggle Public Links",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                    {
                        "custom_id": "toggle_voice_create",
                        "label": "Toggle Create Voice Channels",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                    {
                        "custom_id": "toggle_use_max_bitrate",
                        "label": "Toggle Use Max Bitrate",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                ],
                "type": discord.ComponentType.action_row.value,
            },
            {
                "components": [
                    {
                        "custom_id": "refresh_setup",
                        "label": "Refresh",
                        "style": discord.ButtonStyle.secondary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                ],
                "type": discord.ComponentType.action_row.value,
            },
        ]
        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "These are the current settings for SpellBot on this server. "
                "Please use the buttons below, as well as the `/set` commands, "
                "to setup SpellBot as you wish.\n\n"
                "You may also view Awards configuration using the `/awards` "
                "command and Channels configuration using the `/channels` command."
            ),
            "fields": [
                {"inline": False, "name": "MOTD", "value": self.guild.motd},
                {"inline": True, "name": "Public Links", "value": "❌ Off"},
                {"inline": True, "name": "Create Voice Channels", "value": "❌ Off"},
                {"inline": True, "name": "Use Max Bitrate", "value": "❌ Off"},
            ],
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Setup for {self.guild.name}",
            "type": "rich",
            "flags": 0,
        }


@pytest.mark.asyncio
class TestSetupView(InteractionMixin):
    @pytest_asyncio.fixture
    async def admin(self, factories: Factories, mocker: MockerFixture) -> discord.User:
        mocker.patch("spellbot.views.setup_view.is_admin", MagicMock(return_value=True))
        return mock_discord_user(factories.user.create())

    @pytest_asyncio.fixture
    async def non_admin(self, factories: Factories) -> discord.User:
        return mock_discord_user(factories.user.create())

    async def test_setup_when_admin(self, view: SetupView, admin: discord.User) -> None:
        self.interaction.user = admin
        await view.interaction_check(self.interaction)

    async def test_setup_when_not_admin(self, view: SetupView, non_admin: discord.User) -> None:
        self.interaction.user = non_admin
        with pytest.raises(AdminOnlyError):
            await view.interaction_check(self.interaction)


@pytest.mark.asyncio
class TestCogAdminMotd(InteractionMixin):
    async def test_set_motd(self, cog: AdminCog) -> None:
        await self.run(cog.motd, message="this is a test")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Message of the day updated.",
            ephemeral=True,
        )
        guild = DatabaseSession.query(Guild).one()
        assert guild.motd == "this is a test"

        await self.run(cog.motd)
        DatabaseSession.expire_all()
        guild = DatabaseSession.query(Guild).one()
        assert guild.motd == ""


@pytest.mark.asyncio
class TestCogAdminSuggestVCCategory(InteractionMixin):
    async def test_set_suggest_vc_category(self, cog: AdminCog) -> None:
        await self.run(cog.set_suggest_vc_category, category="whatever")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            'Suggested voice channels category prefix set to "whatever".',
            ephemeral=True,
        )
        guild = DatabaseSession.query(Guild).one()
        assert guild.suggest_voice_category == "whatever"

        self.interaction.response.send_message.reset_mock()  # type: ignore
        await self.run(cog.set_suggest_vc_category)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Suggested voice channels turned off.",
            ephemeral=True,
        )
        DatabaseSession.expire_all()
        guild = DatabaseSession.query(Guild).one()
        assert guild.suggest_voice_category is None

    async def test_set_suggest_vc_category_when_voice_create_on(
        self,
        cog: AdminCog,
        view: SetupView,
    ) -> None:
        """You can't set the suggested vc category when voice create is on."""
        await view.toggle_voice_create.callback(self.interaction)

        await self.run(cog.set_suggest_vc_category, category="whatever")

        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            (
                "Voice channel creation is enabled for this server. "
                "There's no need to suggest existing voice channels. "
                "New channels will be created automatically."
            ),
            ephemeral=True,
        )
        guild = DatabaseSession.query(Guild).one()
        assert guild.suggest_voice_category is None

    async def test_toggle_voice_create_on_when_suggest_vc_category_set(
        self,
        cog: AdminCog,
        view: SetupView,
    ) -> None:
        """Setting the voice create feature on clears the suggested vc category."""
        await self.run(cog.set_suggest_vc_category, category="whatever")

        await view.toggle_voice_create.callback(self.interaction)

        guild = DatabaseSession.query(Guild).one()
        assert guild.suggest_voice_category is None


@pytest.mark.asyncio
class TestCogAdminSetupView(InteractionMixin):
    async def test_refresh_setup(self, view: SetupView) -> None:
        await view.refresh_setup.callback(self.interaction)

        assert self.last_edit_message("view") == [
            {
                "components": [
                    {
                        "custom_id": "toggle_show_links",
                        "label": "Toggle Public Links",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                    {
                        "custom_id": "toggle_voice_create",
                        "label": "Toggle Create Voice Channels",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                    {
                        "custom_id": "toggle_use_max_bitrate",
                        "label": "Toggle Use Max Bitrate",
                        "style": discord.ButtonStyle.primary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                ],
                "type": discord.ComponentType.action_row.value,
            },
            {
                "components": [
                    {
                        "custom_id": "refresh_setup",
                        "label": "Refresh",
                        "style": discord.ButtonStyle.secondary.value,
                        "type": discord.ComponentType.button.value,
                        "disabled": False,
                    },
                ],
                "type": discord.ComponentType.action_row.value,
            },
        ]
        assert self.last_edit_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "These are the current settings for SpellBot on this server. "
                "Please use the buttons below, as well as the `/set` commands, "
                "to setup SpellBot as you wish.\n\n"
                "You may also view Awards configuration using the `/awards` "
                "command and Channels configuration using the `/channels` command."
            ),
            "fields": [
                {"inline": False, "name": "MOTD", "value": self.guild.motd},
                {"inline": True, "name": "Public Links", "value": "❌ Off"},
                {"inline": True, "name": "Create Voice Channels", "value": "❌ Off"},
                {"inline": True, "name": "Use Max Bitrate", "value": "❌ Off"},
            ],
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Setup for {self.guild.name}",
            "type": "rich",
            "flags": 0,
        }

    async def test_toggle_show_links(self, view: SetupView) -> None:
        await view.toggle_show_links.callback(self.interaction)

        self.interaction.edit_original_response.assert_called_once()  # type: ignore
        guild = DatabaseSession.query(Guild).one()
        assert guild.show_links != Guild.show_links.default.arg  # type: ignore

    async def test_toggle_voice_create(self, view: SetupView) -> None:
        await view.toggle_voice_create.callback(self.interaction)

        self.interaction.edit_original_response.assert_called_once()  # type: ignore
        guild = DatabaseSession.query(Guild).one()
        assert guild.voice_create != Guild.voice_create.default.arg  # type: ignore

    async def test_toggle_use_max_bitrate(self, view: SetupView) -> None:
        await view.toggle_use_max_bitrate.callback(self.interaction)

        self.interaction.edit_original_response.assert_called_once()  # type: ignore
        guild = DatabaseSession.query(Guild).one()
        assert guild.use_max_bitrate != Guild.voice_create.default.arg  # type: ignore


@pytest.mark.asyncio
class TestCogAdminInfo(InteractionMixin):
    async def test_happy_path(
        self,
        cog: AdminCog,
        game: Game,
    ) -> None:
        await self.run(cog.info, game_id=f"SB#{game.id}")
        assert self.last_send_message("embed") == {
            "color": self.settings.EMPTY_EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n\n"
                f"{game.guild.motd}\n\n{game.channel.motd}"
            ),
            "fields": [
                {"inline": True, "name": "Format", "value": "Commander"},
                {"inline": True, "name": "Updated at", "value": ANY},
                {"inline": False, "name": "Support SpellBot", "value": ANY},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": self.settings.THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
            "flags": 0,
        }

    async def test_non_numeric_game_id(self, cog: AdminCog) -> None:
        await self.run(cog.info, game_id="bogus")
        self.interaction.response.send_message.assert_awaited_once_with(  # type: ignore
            "There is no game with that ID.",
            ephemeral=True,
        )

    async def test_non_existant_game_id(self, cog: AdminCog) -> None:
        await self.run(cog.info, game_id="1")
        self.interaction.response.send_message.assert_awaited_once_with(  # type: ignore
            "There is no game with that ID.",
            ephemeral=True,
        )


@pytest.mark.asyncio
class TestCogAdminChannels(InteractionMixin):
    async def test_default_seats(self, cog: AdminCog) -> None:
        seats = Channel.default_seats.default.arg - 1  # type: ignore
        await self.run(cog.default_seats, seats=seats)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Default seats set to {seats} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_seats == seats

    async def test_default_format(self, cog: AdminCog) -> None:
        format = Channel.default_format.default.arg + 1  # type: ignore
        await self.run(cog.default_format, format=format)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Default format set to {GameFormat(format)} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_format == format

    async def test_default_bracket(self, cog: AdminCog) -> None:
        bracket = Channel.default_bracket.default.arg + 1  # type: ignore
        await self.run(cog.default_bracket, bracket=bracket)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Default bracket set to {GameBracket(bracket)} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_bracket == bracket

    async def test_default_service(self, cog: AdminCog) -> None:
        service = Channel.default_service.default.arg + 1  # type: ignore
        await self.run(cog.default_service, service=service)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Default service set to {GameService(service)} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.default_service == service

    async def test_auto_verify(self, cog: AdminCog) -> None:
        default_value = Channel.auto_verify.default.arg  # type: ignore
        await self.run(cog.auto_verify, setting=not default_value)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Auto verification set to {not default_value} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.auto_verify != default_value

    async def test_verified_only(self, cog: AdminCog) -> None:
        default_value = Channel.verified_only.default.arg  # type: ignore
        await self.run(cog.verified_only, setting=not default_value)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Verified only set to {not default_value} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.verified_only != default_value

    async def test_unverified_only(self, cog: AdminCog) -> None:
        default_value = Channel.unverified_only.default.arg  # type: ignore
        await self.run(cog.unverified_only, setting=not default_value)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Unverified only set to {not default_value} for this channel.",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.unverified_only != default_value

    async def test_voice_category(self, cog: AdminCog) -> None:
        default_value = Channel.voice_category.default.arg  # type: ignore
        new_value = "wotnot" + default_value
        await self.run(cog.voice_category, prefix=new_value)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Voice category prefix for this channel has been set to: {new_value}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.voice_category != default_value

    async def test_channel_motd(self, cog: AdminCog) -> None:
        motd = "this is a channel message of the day"
        await self.run(cog.channel_motd, message=motd)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Message of the day for this channel has been set to: {motd}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.motd == motd

        await self.run(cog.channel_motd)
        DatabaseSession.expire_all()
        channel = DatabaseSession.query(Channel).one()
        assert channel.motd == ""

    async def test_channel_extra(self, cog: AdminCog) -> None:
        extra = "this is some extra content"
        await self.run(cog.channel_extra, message=extra)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Extra message for this channel has been set to: {extra}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.extra == extra

        await self.run(cog.channel_extra)
        DatabaseSession.expire_all()
        channel = DatabaseSession.query(Channel).one()
        assert channel.extra == ""

    async def test_channels(self, cog: AdminCog, add_channel: Callable[..., Channel]) -> None:
        channel1 = add_channel(auto_verify=True)
        channel2 = add_channel(unverified_only=True)
        channel3 = add_channel(verified_only=True)
        channel4 = add_channel(default_seats=2)

        with mock_operations(admin_action):
            await self.run(cog.channels)

            mock_call = admin_action.safe_send_channel
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.INFO_EMBED_COLOR,
                "description": (
                    f"• <#{channel1.xid}> ({channel1.xid}) — `auto_verify`\n"
                    f"• <#{channel2.xid}> ({channel2.xid}) — `unverified_only`\n"
                    f"• <#{channel3.xid}> ({channel3.xid}) — `verified_only`\n"
                    f"• <#{channel4.xid}> ({channel4.xid}) — `default_seats=2`\n"
                ),
                "thumbnail": {"url": self.settings.ICO_URL},
                "title": f"Configuration for channels in {self.guild.name}",
                "type": "rich",
                "flags": 0,
            }

    async def test_channels_when_invalid_page(
        self,
        cog: AdminCog,
        add_channel: Callable[..., Channel],
    ) -> None:
        add_channel(auto_verify=True)

        with mock_operations(admin_action):
            await self.run(cog.channels, page=2)

            admin_action.safe_send_channel.assert_called_once_with(
                self.interaction,
                "Invalid page.",
                ephemeral=True,
            )

    async def test_channels_when_channel_deleted(
        self,
        cog: AdminCog,
        add_channel: Callable[..., Channel],
    ) -> None:
        add_channel(auto_verify=True)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = None

            await self.run(cog.channels)

            mock_call = admin_action.safe_send_channel
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.INFO_EMBED_COLOR,
                "description": (
                    "**All channels on this server have a default configuration.**\n\n"
                    "Use may use channel specific `/set` commands within a channel "
                    "to change that channel's configuration."
                ),
                "thumbnail": {"url": self.settings.ICO_URL},
                "title": f"Configuration for channels in {self.guild.name}",
                "type": "rich",
                "flags": 0,
            }

    async def test_forget_channel(self, cog: AdminCog, add_channel: Callable[..., Channel]) -> None:
        channel = add_channel(auto_verify=True)

        await self.run(cog.forget_channel, channel=str(channel.xid))
        self.interaction.response.send_message.reset_mock()  # type: ignore

        with mock_operations(admin_action):
            await self.run(cog.channels)

            mock_call = admin_action.safe_send_channel
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.INFO_EMBED_COLOR,
                "description": (
                    "**All channels on this server have a default configuration.**\n\n"
                    "Use may use channel specific `/set` commands within a channel "
                    "to change that channel's configuration."
                ),
                "thumbnail": {"url": self.settings.ICO_URL},
                "title": f"Configuration for channels in {self.guild.name}",
                "type": "rich",
                "flags": 0,
            }

    async def test_forget_channel_when_channel_invalid(
        self,
        cog: AdminCog,
        channel: Channel,
    ) -> None:
        await self.run(cog.forget_channel, channel="foobar")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Invalid ID.",
            ephemeral=True,
        )

    async def test_channels_when_no_non_default_channels(
        self,
        cog: AdminCog,
        channel: Channel,
    ) -> None:
        with mock_operations(admin_action):
            await self.run(cog.channels)

            mock_call = admin_action.safe_send_channel
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.INFO_EMBED_COLOR,
                "description": (
                    "**All channels on this server have a default configuration.**\n\n"
                    "Use may use channel specific `/set` commands within a channel"
                    " to change that channel's configuration."
                ),
                "thumbnail": {"url": self.settings.ICO_URL},
                "title": f"Configuration for channels in {self.guild.name}",
                "type": "rich",
                "flags": 0,
            }

    @pytest.mark.parametrize("page", [1, 2])
    async def test_channels_with_pagination(self, cog: AdminCog, page: int) -> None:
        self.factories.channel.create_batch(
            100,
            guild=self.guild,
            default_seats=2,
            auto_verify=True,
            unverified_only=True,
            verified_only=True,
        )

        with mock_operations(admin_action):
            await self.run(cog.channels, page=page)

            mock_call = admin_action.safe_send_channel
            assert (
                mock_call.call_args_list[0].kwargs["embed"].to_dict()["footer"]["text"]
                == f"page {page} of 3"
            )


@pytest.mark.asyncio
class TestCogAdminAwards(InteractionMixin):
    async def test_awards(self, cog: AdminCog) -> None:
        award1 = self.factories.guild_award.create(
            guild=self.guild,
            count=10,
            role="role1",
            message="msg1",
        )
        award2 = self.factories.guild_award.create(
            guild=self.guild,
            count=20,
            role="role2",
            message="msg2",
        )
        award3 = self.factories.guild_award.create(
            guild=self.guild,
            count=30,
            role="role3",
            message="msg3",
        )

        await self.run(cog.awards)

        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                f"• **ID {award1.id}** — _after {award1.count}"
                f" games_ — give `@{award1.role}` — {award1.message}\n"
                f"• **ID {award2.id}** — _after {award2.count}"
                f" games_ — give `@{award2.role}` — {award2.message}\n"
                f"• **ID {award3.id}** — _after {award3.count}"
                f" games_ — give `@{award3.role}` — {award3.message}\n"
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Player Awards for {self.guild.name}",
            "type": "rich",
            "flags": 0,
        }

    async def test_awards_when_invalid_page(self, cog: AdminCog) -> None:
        await self.run(cog.awards, page=2)

        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Invalid page.",
            ephemeral=True,
        )

    async def test_awards_when_no_awards(self, cog: AdminCog) -> None:
        await self.run(cog.awards)
        assert self.last_send_message("embed") == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "**There are no awards configured on this server.**\n\n"
                "To add awards use the `/award add` command."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "title": f"SpellBot Player Awards for {self.guild.name}",
            "type": "rich",
            "flags": 0,
        }

    @pytest.mark.parametrize("page", [1, 2])
    async def test_awards_with_pagination(self, cog: AdminCog, page: int) -> None:
        self.factories.guild_award.create_batch(
            40,
            guild=self.guild,
            count=10,
            role="this-is-a-role-name",
            message="mm" * 50,
        )
        await self.run(cog.awards, page=page)
        assert self.last_send_message("embed")["footer"]["text"] == f"page {page} of 2"

    async def test_award_delete(self, cog: AdminCog) -> None:
        awards = self.factories.guild_award.create_batch(2, guild=self.guild)
        await self.run(cog.award_delete, id=awards[0].id)
        assert self.last_send_message("embed") == {
            "author": {"name": "Award deleted!"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": "You can view all awards with the `/awards` command.",
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }
        assert self.last_send_message("ephemeral")
        assert DatabaseSession.query(GuildAward).count() == 1

    async def test_award_add(self, cog: AdminCog) -> None:
        await self.run(cog.award_add, count=10, role="role", message="message", repeating=True)
        award = DatabaseSession.query(GuildAward).one()
        assert self.last_send_message("embed") == {
            "author": {"name": "Award added!"},
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                f"• **ID {award.id}** — _every 10 games_ — give `@role` — message\n\n"
                "You can view all awards with the `/awards` command."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
            "flags": 0,
        }
        assert self.last_send_message("ephemeral")
        assert award.count == 10
        assert award.role == "role"
        assert award.message == "message"
        assert award.repeating

    async def test_award_add_when_verified_and_unverified(self, cog: AdminCog) -> None:
        await self.run(
            cog.award_add,
            count=10,
            role="role",
            message="message",
            verified_only=True,
            unverified_only=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 0
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Your award can't be both verified and unverifed only.",
            ephemeral=True,
        )

    async def test_award_add_message_too_long(self, cog: AdminCog) -> None:
        message = "hippo " * 300
        await self.run(cog.award_add, count=1, role="role", message=message)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "Your message can't be longer than 500 characters.",
            ephemeral=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 0

    async def test_award_add_zero_count(self, cog: AdminCog) -> None:
        await self.run(cog.award_add, count=0, role="role", message="message")
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You can't create an award for zero games played.",
            ephemeral=True,
        )
        assert DatabaseSession.query(GuildAward).count() == 0


@pytest.mark.asyncio
class TestCogAdminDeleteExpired(InteractionMixin):
    @pytest.mark.parametrize("setting", [True, False])
    async def test_set_delete_expired(self, cog: AdminCog, setting: bool) -> None:
        await self.run(cog.delete_expired, setting=setting)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Delete expired setting for this channel has been set to: {setting}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.delete_expired is setting


@pytest.mark.asyncio
class TestCogAdminVoiceInvite(InteractionMixin):
    @pytest.mark.parametrize("setting", [True, False])
    async def test_set_voice_invite(self, cog: AdminCog, setting: bool) -> None:
        await self.run(cog.voice_invite, setting=setting)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Voice invite setting for this channel has been set to: {setting}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.voice_invite is setting


@pytest.mark.asyncio
class TestCogAdminBlindGames(InteractionMixin):
    @pytest.mark.parametrize("setting", [True, False])
    async def test_set_blind_games(self, cog: AdminCog, setting: bool) -> None:
        await self.run(cog.blind_games, setting=setting)
        self.interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"Hidden player names for this channel has been set to: {setting}",
            ephemeral=True,
        )
        channel = DatabaseSession.query(Channel).one()
        assert channel.blind_games is setting


@pytest.mark.asyncio
class TestCogAdminMythicTrack(InteractionMixin):
    @pytest.mark.parametrize("initial_setting", [True, False])
    async def test_setup_mythic_track(self, cog: AdminCog, initial_setting: bool) -> None:
        self.guild.enable_mythic_track = initial_setting  # type: ignore
        DatabaseSession.commit()

        await self.run(cog.setup_mythic_track)

        self.interaction.response.send_message.assert_called_once()  # type: ignore
        guild = DatabaseSession.query(Guild).one()
        assert guild.enable_mythic_track != initial_setting
