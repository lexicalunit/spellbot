from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import discord
import pytest

from spellbot import services
from spellbot.models import GameStatus, WebActionKind, WebActionStatus
from spellbot.web.api import play

if TYPE_CHECKING:
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

    WebClient = TestClient[web.Request, web.Application]

pytestmark = pytest.mark.use_db

GUILD_XID = 920001
CHANNEL_XID = 920002
VIEWER_XID = 920003
OTHER_XID = 920004

PLAYABLE = discord.Permissions(
    view_channel=True,
    send_messages=True,
    use_application_commands=True,
)
NO_SEND = discord.Permissions(view_channel=True, use_application_commands=True)


@pytest.fixture(autouse=True)
def block_icon_backfill(mocker: MockerFixture) -> None:
    """Stop the guild-icon backfill from making a real Discord REST call."""
    mocker.patch(
        "spellbot.services.guilds.fetch_icon_url",
        AsyncMock(return_value=None),
    )


def login(mocker: MockerFixture, xid: int | None = VIEWER_XID, name: str = "Viewer") -> None:
    """Present the request as a logged-in viewer to every module that resolves one."""
    result = (xid, name) if xid is not None else (None, None)
    mocker.patch("spellbot.web.api.play.get_viewer", AsyncMock(return_value=result))
    mocker.patch("spellbot.web.api.viewer_auth.get_viewer", AsyncMock(return_value=result))


def allow(mocker: MockerFixture, perms: discord.Permissions = PLAYABLE) -> AsyncMock:
    """Make Discord report `perms` for whoever is being checked."""
    stub = AsyncMock(return_value=perms)
    mocker.patch("spellbot.web.api.play.discord_api.member_channel_permissions", stub)
    return stub


def seed(factories: Factories, *, played: bool = True, **guild_kwargs: Any) -> Any:
    """Create a guild, a channel, the viewer, and (by default) a play record linking them."""
    guild = factories.guild.create(xid=GUILD_XID, name="Test Guild", **guild_kwargs)
    channel = factories.channel.create(xid=CHANNEL_XID, guild=guild, name="games")
    user = factories.user.create(xid=VIEWER_XID, name="Viewer")
    if played:
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=4,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(tz=UTC).replace(tzinfo=None),
        )
        factories.play.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)
    return guild, channel, user


def pending_game(factories: Factories, guild: Any, channel: Any, *, players: list[Any]) -> Any:
    game = factories.game.create(guild=guild, channel=channel, seats=4)
    for player in players:
        factories.queue.create(user_xid=player.xid, game_id=game.id, og_guild_xid=guild.xid)
    return game


@pytest.mark.asyncio
class TestPlayPage:
    async def test_requires_login(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker, xid=None)
        resp = await client.get("/play", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/login?next=/play"

    async def test_lists_played_servers(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        resp = await client.get("/play")
        assert resp.status == 200
        body = await resp.text()
        assert "Test Guild" in body
        assert f"/play/g/{GUILD_XID}" in body

    async def test_lists_servers_that_opted_out_of_promotion(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # Opting out of being advertised publicly is not the same as hiding the server
        # from the people who already play in it.
        seed(factories, promote=False)
        login(mocker)
        resp = await client.get("/play")
        assert "Test Guild" in await resp.text()

    async def test_marks_servers_that_turned_the_feature_off(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories, web_games=False)
        login(mocker)
        body = await (await client.get("/play")).text()
        assert "Turned off" in body
        assert f'href="/play/g/{GUILD_XID}"' not in body

    async def test_empty_when_the_viewer_has_never_played(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories, played=False)
        login(mocker)
        body = await (await client.get("/play")).text()
        assert "haven&#39;t played a SpellBot game" in body


@pytest.mark.asyncio
class TestPlayGuildPage:
    async def test_requires_login(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker, xid=None)
        resp = await client.get(f"/play/g/{GUILD_XID}", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == f"/login?next=/play/g/{GUILD_XID}"

    async def test_non_numeric_guild_is_404(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        login(mocker)
        assert (await client.get("/play/g/nope")).status == 404

    async def test_unknown_guild_is_404(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker)
        assert (await client.get("/play/g/123456")).status == 404

    async def test_banned_guild_is_404(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories, banned=True)
        login(mocker)
        assert (await client.get(f"/play/g/{GUILD_XID}")).status == 404

    async def test_shows_the_create_form_for_a_playable_channel(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert "Start a game" in body
        assert "#games" in body
        assert "disabled" not in body.split("create-channel")[1].split("</select>")[0]

    async def test_channel_is_disabled_when_the_viewer_cannot_post(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker, NO_SEND)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert "you can&#39;t post here" in body
        assert "disabled" in body.split("create-channel")[1].split("</select>")[0]

    async def test_channel_is_disabled_when_the_viewer_left_the_server(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        mocker.patch(
            "spellbot.web.api.play.discord_api.member_channel_permissions",
            AsyncMock(return_value=None),
        )
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert "you&#39;re not in this server" in body

    async def test_lists_a_joinable_pending_game(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, _ = seed(factories)
        other = factories.user.create(xid=OTHER_XID, name="Other")
        game = pending_game(factories, guild, channel, players=[other])
        login(mocker)
        allow(mocker)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert f'data-game-id="{game.id}"' in body
        assert "1 of 4 seats" in body
        assert 'data-action="join"' in body

    async def test_offers_leave_for_a_game_the_viewer_is_in(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, user = seed(factories)
        pending_game(factories, guild, channel, players=[user])
        login(mocker)
        allow(mocker)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert 'data-action="leave"' in body
        assert 'data-action="join"' not in body

    async def test_hides_games_in_channels_the_viewer_cannot_use(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, _ = seed(factories)
        other = factories.user.create(xid=OTHER_XID, name="Other")
        game = pending_game(factories, guild, channel, players=[other])
        login(mocker)
        allow(mocker, NO_SEND)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert f'data-game-id="{game.id}"' not in body

    async def test_says_so_when_the_server_turned_the_feature_off(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories, web_games=False)
        login(mocker)
        allow(mocker)
        body = await (await client.get(f"/play/g/{GUILD_XID}")).text()
        assert "turned off creating and joining games" in body
        assert "Start a game" not in body


@pytest.mark.asyncio
class TestPlayCreate:
    def url(self, channel_xid: int = CHANNEL_XID) -> str:
        return f"/play/g/{GUILD_XID}/c/{channel_xid}/create"

    async def test_requires_login(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker, xid=None)
        resp = await client.post(self.url())
        assert resp.status == 401
        assert (await resp.json())["error"] == "not_logged_in"

    async def test_enqueues_a_pending_action(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url(), data={"format": "1", "seats": "4"})
        assert resp.status == 200
        payload = await resp.json()
        assert payload["ok"] is True
        assert payload["status"] == WebActionStatus.PENDING.value
        action = await services.web_actions.get(payload["action_id"], user_xid=VIEWER_XID)
        assert action is not None
        assert action.kind == WebActionKind.CREATE.value
        assert action.guild_xid == GUILD_XID
        assert action.channel_xid == CHANNEL_XID
        assert action.params == {"format": 1, "seats": 4}

    async def test_refuses_a_channel_the_viewer_has_never_played_in(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # Otherwise the website would be a way to post into any channel of any server
        # the bot happens to be in.
        guild, _, _ = seed(factories)
        stranger = factories.channel.create(xid=920099, guild=guild, name="staff-only")
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url(stranger.xid))
        assert resp.status == 403
        assert (await resp.json())["error"] == "channel_not_played"

    async def test_refuses_when_the_viewer_cannot_post_there(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker, NO_SEND)
        resp = await client.post(self.url())
        assert resp.status == 403
        assert (await resp.json())["error"] == "no_send"

    async def test_refuses_when_the_viewer_is_no_longer_a_member(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        mocker.patch(
            "spellbot.web.api.play.discord_api.member_channel_permissions",
            AsyncMock(return_value=None),
        )
        resp = await client.post(self.url())
        assert resp.status == 403
        assert (await resp.json())["error"] == "not_a_member"

    async def test_refuses_a_banned_user(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        await services.users.set_banned(VIEWER_XID, banned=True)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url())
        assert resp.status == 403
        assert (await resp.json())["error"] == "user_banned"

    async def test_refuses_when_the_server_turned_the_feature_off(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories, web_games=False)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url())
        assert resp.status == 403
        assert (await resp.json())["error"] == "web_games_disabled"

    async def test_refuses_a_verified_only_channel_for_an_unverified_viewer(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        await services.channels.update_settings(CHANNEL_XID, verified_only=True)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url())
        assert resp.status == 403
        assert (await resp.json())["error"] == "verified_only"

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            pytest.param("format", "9999", "invalid_format", id="format"),
            pytest.param("bracket", "9999", "invalid_bracket", id="bracket"),
            pytest.param("service", "9999", "invalid_service", id="service"),
            pytest.param("seats", "99", "invalid_seats", id="seats_high"),
            pytest.param("seats", "1", "invalid_seats", id="seats_low"),
            pytest.param("seats", "abc", "invalid_seats", id="seats_nan"),
        ],
    )
    async def test_rejects_out_of_range_values(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
        field: str,
        value: str,
        expected: str,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url(), data={field: value})
        assert resp.status == 400
        assert (await resp.json())["error"] == expected

    async def test_ignores_a_posted_friends_list(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # Accepting arbitrary user ids here would be a way to drag people into games
        # they never chose to be in.
        seed(factories)
        login(mocker)
        allow(mocker)
        resp = await client.post(self.url(), data={"friends": f"<@{OTHER_XID}>"})
        payload = await resp.json()
        action = await services.web_actions.get(payload["action_id"], user_xid=VIEWER_XID)
        assert action is not None
        assert "friends" not in action.params


@pytest.mark.asyncio
class TestPlayJoinAndLeave:
    async def test_join_enqueues_against_the_games_channel(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, _ = seed(factories)
        other = factories.user.create(xid=OTHER_XID, name="Other")
        game = pending_game(factories, guild, channel, players=[other])
        login(mocker)
        allow(mocker)
        resp = await client.post(f"/play/game/{game.id}/join")
        assert resp.status == 200
        action = await services.web_actions.get(
            (await resp.json())["action_id"],
            user_xid=VIEWER_XID,
        )
        assert action is not None
        assert action.kind == WebActionKind.JOIN.value
        assert action.game_id == game.id
        assert action.channel_xid == CHANNEL_XID

    async def test_leave_enqueues(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, user = seed(factories)
        game = pending_game(factories, guild, channel, players=[user])
        login(mocker)
        allow(mocker)
        resp = await client.post(f"/play/game/{game.id}/leave")
        assert resp.status == 200
        action = await services.web_actions.get(
            (await resp.json())["action_id"],
            user_xid=VIEWER_XID,
        )
        assert action is not None
        assert action.kind == WebActionKind.LEAVE.value

    async def test_unknown_game_is_404(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker)
        resp = await client.post("/play/game/123456/join")
        assert resp.status == 404
        assert (await resp.json())["error"] == "game_unavailable"

    async def test_started_game_is_refused(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, _ = seed(factories)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=4,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(tz=UTC).replace(tzinfo=None),
        )
        login(mocker)
        allow(mocker)
        resp = await client.post(f"/play/game/{game.id}/join")
        assert resp.status == 409
        assert (await resp.json())["error"] == "game_started"

    async def test_join_is_refused_when_permissions_were_revoked(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild, channel, _ = seed(factories)
        other = factories.user.create(xid=OTHER_XID, name="Other")
        game = pending_game(factories, guild, channel, players=[other])
        login(mocker)
        allow(mocker, NO_SEND)
        resp = await client.post(f"/play/game/{game.id}/join")
        assert resp.status == 403


@pytest.mark.asyncio
class TestPlayActionStatus:
    async def test_reports_a_finished_action(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        allow(mocker)
        action = await services.web_actions.enqueue(
            user_xid=VIEWER_XID,
            guild_xid=GUILD_XID,
            channel_xid=CHANNEL_XID,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        await services.web_actions.resolve(action.id, notices=["posted"])
        resp = await client.get(f"/play/action/{action.id}.json")
        assert resp.status == 200
        payload = await resp.json()
        assert payload["ok"] is True
        assert payload["status"] == WebActionStatus.DONE.value
        assert payload["notices"] == ["posted"]

    async def test_reports_an_error_code(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        action = await services.web_actions.enqueue(
            user_xid=VIEWER_XID,
            guild_xid=GUILD_XID,
            channel_xid=CHANNEL_XID,
            kind=WebActionKind.JOIN.value,
            locale="en",
        )
        await services.web_actions.resolve(action.id, error_code="missing_permissions")
        payload = await (await client.get(f"/play/action/{action.id}.json")).json()
        assert payload["ok"] is False
        assert payload["error"] == "missing_permissions"

    async def test_another_users_action_is_404(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        factories.user.create(xid=OTHER_XID, name="Other")
        action = await services.web_actions.enqueue(
            user_xid=OTHER_XID,
            guild_xid=GUILD_XID,
            channel_xid=CHANNEL_XID,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        login(mocker)
        assert (await client.get(f"/play/action/{action.id}.json")).status == 404

    async def test_requires_login(self, client: WebClient, mocker: MockerFixture) -> None:
        login(mocker, xid=None)
        assert (await client.get("/play/action/1.json")).status == 401


class TestErrorMessages:
    def test_every_reportable_code_has_a_message(self) -> None:
        # A code with no entry would surface to the user as a generic failure, hiding
        # the actual reason, so the catalog must cover every code we can emit.
        messages = play.error_messages("en")
        for code in play.REQUEST_ERROR_CODES:
            assert messages[code]
            assert "web.play.error" not in messages[code]

    def test_every_blocked_reason_has_a_label(self) -> None:
        labels = play.blocked_messages("en")
        for code in play.BLOCKED_CODES:
            assert labels[code]
            assert "web.play.blocked" not in labels[code]


@pytest.mark.asyncio
class TestPlayNavigation:
    async def test_other_pages_link_to_play_when_logged_in(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # The feature is useless if nobody can find it, so the shared header links to it.
        seed(factories)
        login(mocker)
        body = await (await client.get("/queues")).text()
        assert 'href="/play"' in body

    async def test_the_play_page_does_not_link_to_itself(
        self,
        client: WebClient,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        seed(factories)
        login(mocker)
        body = await (await client.get("/play")).text()
        assert 'class="site-nav__link" href="/play"' not in body

    async def test_logged_out_visitors_see_no_play_link(
        self,
        client: WebClient,
        mocker: MockerFixture,
    ) -> None:
        login(mocker, xid=None)
        body = await (await client.get("/queues")).text()
        assert 'href="/play"' not in body
