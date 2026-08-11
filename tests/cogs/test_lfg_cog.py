# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import discord
import pytest
from sqlalchemy import func, select, update

from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.cogs.lfg_cog import guild_war_autocomplete
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.integrations import convoke
from spellbot.models import Channel, Game, GameStatus, Guild, Queue, User
from spellbot.views import GameView
from tests.fixtures import Factories, run_command
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db

CONVOKE_PENDING_MSG = (
    "_A [Convoke](https://www.convoke.games/) link will be created when all players have joined._"
)


SUPPORT_CTA = (
    "\n\n-# **Support SpellBot** — "
    "Become [a patron](https://www.patreon.com/lexicalunit) "
    "or give a [one-off tip](https://ko-fi.com/lexicalunit)."
)


@pytest.fixture
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_lfg(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 123
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.lfg, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                content=None,
                embed=ANY,
                view=ANY,
                allowed_mentions=ANY,
            )
            # check that the view (join/leave buttons) exists for pending games:
            assert isinstance(lfg_action.safe_followup_channel.call_args.kwargs["view"], GameView)

        # Find the user created by this interaction
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == interaction.user.id))
        ).scalar_one()
        # Find the game created in this channel
        game = (
            (
                await DatabaseSession.execute(
                    select(Game)
                    .where(
                        Game.channel_xid == channel.xid,  # type: ignore
                        Game.guild_xid == guild.xid,
                    )
                    .order_by(Game.id.desc()),
                )
            )
            .scalars()
            .first()
        )
        assert game is not None
        assert game.channel_xid == channel.xid
        assert game.guild_xid == guild.xid
        assert interaction.channel is not None
        user_game = await user.game(interaction.channel.id)
        assert user_game is not None
        assert user_game.id == game.id

    async def test_lfg_fully_seated(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        settings: Settings,
    ) -> None:
        channel = add_channel(
            default_format=GameFormat.MODERN.value,
            default_service=GameService.COCKATRICE.value,
            default_seats=2,
            xid=interaction.channel_id,
        )
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.COCKATRICE.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=123)

        other_user = factories.user.create(xid=interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)

        with mock_operations(lfg_action, users=[other_player]):
            message = MagicMock(spec=discord.Message)
            message.id = game.posts[0].message_xid
            lfg_action.safe_get_partial_message.return_value = message

            await run_command(cog.lfg, interaction)

            DatabaseSession.expire_all()
            game = (await DatabaseSession.execute(select(Game))).scalar_one()
            started_at_timestamp = int(
                game.started_at.replace(tzinfo=UTC).timestamp(),
            )
            mock_call = lfg_action.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": settings.STARTED_EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your game details.\n\n"
                    f"{guild.motd}\n\n{channel.motd}"
                )
                + SUPPORT_CTA,
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": (
                            f"• <@{interaction.user.id}> "
                            f"({interaction.user.display_name})\n"
                            f"• <@{other_player.id}> ({other_player.display_name})"
                        ),
                    },
                    {"inline": True, "name": "Format", "value": "Modern"},
                    {
                        "inline": True,
                        "name": "Started at",
                        "value": f"<t:{started_at_timestamp}>",
                    },
                    {"inline": False, "name": "🔔 Notifications", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Cockatrice"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
                "flags": 0,
            }
            # check that the view (join/leave buttons) is removed from fully seated games:
            assert mock_call.call_args_list[0].kwargs["view"] is None

    async def test_lfg_when_blocked(
        self,
        game: Game,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        other_user = factories.user.create(game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction)

        # Verify the original game still exists
        other_game = (
            await DatabaseSession.execute(select(Game).where(Game.id == game.id))
        ).scalar_one()
        assert other_game is not None
        # Verify a new game was created for the user (due to blocking)
        # The user should be in a different game now
        user_game = (
            await DatabaseSession.execute(
                select(Game)
                .join(Queue, Queue.game_id == Game.id)
                .where(Queue.user_xid == user.xid),
            )
        ).scalar_one()
        assert other_game.id != user_game.id

    async def test_lfg_when_already_in_game(
        self,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        channel: Channel,
        bot: SpellBot,
    ) -> None:
        with mock_operations(lfg_action, users=[mock_discord_object(player)]):
            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                "You're already in a game in this channel.",
            )

        found = (
            await DatabaseSession.execute(select(User).where(User.xid == player.xid))
        ).scalar_one()
        assert (await found.game(channel.xid)).id == game.id

    async def test_lfg_with_format(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, format=GameFormat.MODERN.value)
        assert (
            await DatabaseSession.execute(select(Game))
        ).scalar_one().format == GameFormat.MODERN.value

    async def test_lfg_with_seats(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, seats=2)
        assert (await DatabaseSession.execute(select(Game))).scalar_one().seats == 2

    async def test_lfg_with_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 3
        assert all(queue.game_id == game.id for queue in queues)

    async def test_lfg_with_friends_blocked(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=user.xid, blocked_user_xid=friend1.xid)
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_friends_blocked_by(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=friend1.xid, blocked_user_xid=user.xid)
        players = [mock_discord_object(x) for x in (user, friend1, friend2)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_too_many_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        friend3 = factories.user.create()
        friend4 = factories.user.create()
        players = [mock_discord_object(x) for x in (user, friend1, friend2, friend3, friend4)]
        with mock_operations(lfg_action, users=players):
            lfg_action.safe_followup_channel.return_value = message

            cog = LookingForGameCog(bot)
            await run_command(
                cog.lfg,
                interaction,
                friends=f"<@{friend1.xid}><@{friend2.xid}><@{friend3.xid}><@{friend4.xid}>",
            )

        assert not (await DatabaseSession.execute(select(Game))).scalar_one_or_none()

    async def test_lfg_multiple_times(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.lfg, interaction)
        await run_command(cog.lfg, interaction)
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_rematch(
        self,
        cog: LookingForGameCog,
        user: User,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        friend = factories.user.create()
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.GIRUDO.value,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(tz=UTC),
        )
        message = MagicMock(spec=discord.Message)
        message.id = 123
        factories.post.create(
            guild=guild,
            channel=channel,
            game=game,
            message_xid=message.id,
        )
        factories.play.create(user_xid=user.xid, game_id=game.id)
        factories.play.create(user_xid=friend.xid, game_id=game.id)
        players = [mock_discord_object(x) for x in (user, friend)]

        with mock_operations(lfg_action, users=players):
            message = MagicMock(spec=discord.Message)
            message.id = 456
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.rematch, interaction)

            lfg_action.safe_followup_channel.assert_called_once_with(
                interaction,
                content=None,
                embed=ANY,
                view=ANY,
                allowed_mentions=ANY,
            )

        DatabaseSession.expire_all()
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 2

    async def test_start(
        self,
        cog: LookingForGameCog,
        user: User,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=123)
        factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)
        other_user = factories.user.create()
        factories.queue.create(user_xid=other_user.xid, game_id=game.id, og_guild_xid=guild.xid)
        players = [mock_discord_object(x) for x in (user, other_user)]

        with mock_operations(lfg_action, users=players):
            message = MagicMock(spec=discord.Message)
            message.id = 456
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.start, interaction)

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.status == GameStatus.STARTED.value
        assert game.seats == 2


@pytest.mark.asyncio
class TestCogLookingForGameJoinButton:
    async def test_join(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        settings: Settings,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=message,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            mock_call = lfg_action.safe_update_embed_origin
            mock_call.assert_called_once()
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + SUPPORT_CTA,
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"• <@{user.xid}> (user-{user.xid})",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                    {"inline": False, "name": "🔔 Notifications", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_join_when_no_original_response(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_original_response",
                return_value=None,
            ),
        ):
            lfg_action.safe_update_embed_origin.return_value = message
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            lfg_action.safe_update_embed_origin.assert_not_called()

    async def test_join_when_blocked(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        other_user = factories.user.create(xid=user.xid + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        with mock_operations(
            lfg_action,
            users=[
                mock_discord_object(user),
                mock_discord_object(other_user),
            ],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                interaction.user,
                "You can not join this game.",
            )

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_join_when_blocked_with_to_mode(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        # Tournament organizer mode ignores blocks, so the blocked user joins the game.
        other_user = factories.user.create(xid=user.xid + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)
        await DatabaseSession.execute(
            update(Channel).where(Channel.xid == game.channel.xid).values(to_mode=True),
        )
        await DatabaseSession.commit()

        with mock_operations(
            lfg_action,
            users=[
                mock_discord_object(user),
                mock_discord_object(other_user),
            ],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            lfg_action.safe_send_user.assert_not_called()

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1
        DatabaseSession.expire_all()
        assert sorted(p.xid for p in await game.players()) == sorted([user.xid, other_user.xid])

    async def test_join_when_started(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        # fully seat and start the game
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        await DatabaseSession.execute(
            update(Game)
            .where(Game.id == game.id)
            .values(started_at=datetime.now(tz=UTC), status=GameStatus.STARTED.value),
        )
        await DatabaseSession.commit()

        # then try to join it
        with mock_operations(
            lfg_action,
            users=[mock_discord_object(user)],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            lfg_action.safe_send_user.assert_called_once_with(
                interaction.user,
                "Sorry, that game has already started.",
            )

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_join_when_defer_fails(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with (
            mock_operations(lfg_action, users=[mock_discord_object(user)]),
            patch(
                "spellbot.views.lfg_view.safe_defer_interaction",
                return_value=False,
            ),
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            lfg_action.safe_update_embed_origin.assert_not_called()


WAR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
WAR_TITLE = "Summer Clash"


def live_war(
    war_id: str = WAR_ID,
    title: str = WAR_TITLE,
    slug: str = "summer-clash",
) -> dict[str, str]:
    return {"id": war_id, "title": title, "slug": slug, "status": "active"}


@pytest.mark.asyncio
class TestCogWar:
    async def test_war_creates_a_game_tagged_with_the_war(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.resolve_live_guild_war",
            AsyncMock(return_value=live_war()),
        )
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 123
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.war, interaction, war=WAR_ID)

        game = (
            (
                await DatabaseSession.execute(
                    select(Game)
                    .where(
                        Game.guild_xid == guild.xid,
                        Game.channel_xid == channel.xid,  # type: ignore
                    )
                    .order_by(Game.id.desc()),
                )
            )
            .scalars()
            .first()
        )
        assert game is not None
        assert game.war_id == WAR_ID
        assert game.war_title == WAR_TITLE

    async def test_war_forces_convoke_over_a_channel_default(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
        interaction: discord.Interaction,
        guild: Guild,
        mocker: MockerFixture,
    ) -> None:
        # Guild Wars only exist on Convoke, so `/war` must win over a channel that
        # defaults to some other service rather than failing the request.
        add_channel(xid=interaction.channel_id, default_service=GameService.COCKATRICE.value)
        mocker.patch(
            "spellbot.integrations.convoke.resolve_live_guild_war",
            AsyncMock(return_value=live_war()),
        )
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 123
            lfg_action.safe_followup_channel.return_value = message

            await run_command(cog.war, interaction, war=WAR_ID)

        game = (await DatabaseSession.execute(select(Game))).scalars().one()
        assert game.service == GameService.CONVOKE.value
        assert game.war_id == WAR_ID

    async def test_war_with_an_unknown_war_creates_no_game(
        self,
        cog: LookingForGameCog,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.resolve_live_guild_war",
            AsyncMock(return_value=None),
        )
        with mock_operations(lfg_action):
            await run_command(cog.war, interaction, war="not-a-real-war")

            reply = lfg_action.safe_followup_channel.call_args.args[1]
            assert "not available" in reply

        assert (await DatabaseSession.execute(select(func.count(Game.id)))).scalar_one() == 0

    async def test_lfg_no_longer_takes_a_guild_war(self, cog: LookingForGameCog) -> None:
        # Guild Wars moved to their own command; leaving the option on `/lfg` would be
        # a second, harder-to-type way to do the same thing.
        assert "guild_war" not in {param.name for param in cog.lfg.parameters}
        assert "war" in {param.name for param in cog.war.parameters}

    async def test_war_only_offers_seat_counts_a_war_can_hold(
        self,
        cog: LookingForGameCog,
    ) -> None:
        seats = next(param for param in cog.war.parameters if param.name == "seats")
        offered = [choice.value for choice in seats.choices]
        assert offered == list(range(convoke.MIN_WAR_SEATS, convoke.MAX_WAR_SEATS + 1))

    async def test_war_does_not_offer_a_service(self, cog: LookingForGameCog) -> None:
        assert "service" not in {param.name for param in cog.war.parameters}


@pytest.mark.asyncio
class TestGuildWarAutocomplete:
    async def test_lists_every_live_war_when_nothing_is_typed(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(return_value=[live_war(), live_war("id-2", "Winter Clash", "winter-clash")]),
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert [(c.name, c.value) for c in choices] == [
            (WAR_TITLE, WAR_ID),
            ("Winter Clash", "id-2"),
        ]

    async def test_filters_by_title(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(return_value=[live_war(), live_war("id-2", "Winter Clash", "winter-clash")]),
        )
        choices = await guild_war_autocomplete(interaction, "  WINTER ")
        assert [c.value for c in choices] == ["id-2"]

    async def test_filters_by_slug(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        # The slug is what shows up in Convoke URLs, so someone pasting one should
        # still find their war.
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(return_value=[live_war(), live_war("id-2", "Winter Clash", "winter-clash")]),
        )
        choices = await guild_war_autocomplete(interaction, "summer-cl")
        assert [c.value for c in choices] == [WAR_ID]

    async def test_truncates_names_over_the_discord_limit(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(return_value=[live_war(title="W" * 200)]),
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert len(choices[0].name) == 100
        assert choices[0].name.endswith("...")
        # The value is the war id, so truncating the label never breaks selection.
        assert choices[0].value == WAR_ID

    async def test_caps_at_the_discord_choice_limit(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(
                return_value=[live_war(f"id-{i}", f"War {i}", f"war-{i}") for i in range(40)],
            ),
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert len(choices) == 25

    async def test_an_unreachable_convoke_offers_nothing(
        self,
        interaction: discord.Interaction,
        mocker: MockerFixture,
    ) -> None:
        # `get_live_guild_wars` swallows failures and returns []; autocomplete must
        # degrade to an empty list rather than erroring inside Discord's UI.
        mocker.patch(
            "spellbot.integrations.convoke.get_live_guild_wars",
            AsyncMock(return_value=[]),
        )
        assert await guild_war_autocomplete(interaction, "summer") == []
