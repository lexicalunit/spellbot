import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest
import pytz
import redis
from sqlalchemy.orm.session import Session

from spellbot import tasks
from spellbot.data import Game, Server
from spellbot.tasks import (
    begin_background_tasks,
    cleanup_expired_games,
    cleanup_started_games,
    update_average_wait_times,
    update_metrics,
)

from .mocks import AsyncMock
from .mocks.discord import MockMessage
from .mocks.users import AMY, BUDDY, DUDE, FRIEND, GUY, JACOB
from .test_spellbot import all_games, an_admin, game_embed_for, user_has_game


@pytest.mark.asyncio
class TestTasks:
    async def test_game_cleanup_started(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        mentions = [FRIEND, GUY, BUDDY, DUDE]
        mentions_str = " ".join([f"@{user.name}" for user in mentions])
        cmd = f"!game {mentions_str}"
        await client.on_message(MockMessage(an_admin(), channel, cmd, mentions=mentions))
        game = all_games(client)[0]
        assert channel.last_sent_response == (
            f"**Game {game['id']} created:**\n"
            f"> Game: <{game['url']}>\n"
            f"> Spectate: <{game['url']}?spectate=true>\n"
            f"> Players notified by DM: <@{FRIEND.id}>, <@{BUDDY.id}>,"
            f" <@{GUY.id}>, <@{DUDE.id}>"
        )
        player_response = game_embed_for(client, FRIEND, True)
        assert FRIEND.last_sent_embed == player_response
        assert GUY.last_sent_embed == player_response
        assert BUDDY.last_sent_embed == player_response
        assert DUDE.last_sent_embed == player_response

        assert user_has_game(client, FRIEND)

        freezer.move_to(NOW + timedelta(days=3))
        await cleanup_started_games(client)

        assert not user_has_game(client, FRIEND)

    async def test_game_cleanup_expired(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        post = channel.last_sent_message
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        freezer.move_to(NOW + timedelta(days=3))
        await cleanup_expired_games(client)

        assert not user_has_game(client, GUY)

        # post.delete.assert_called()
        assert post.last_edited_call == {
            "args": ("Sorry, this game was expired due to inactivity.",),
            "kwargs": {},
        }

    async def test_game_cleanup_expired_user_moved(
        self, client, freezer, channel_maker, monkeypatch
    ):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg ~modern"))
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        freezer.move_to(NOW + timedelta(days=3))

        # user has moved to a new game
        await client.on_message(MockMessage(GUY, channel, "!leave"))
        await client.on_message(MockMessage(GUY, channel, "!lfg ~legacy"))

        class FakeUser:
            def __init__(self):
                self.game_id = 11  # different game
                self.waiting = True

        class FakeGame:
            def __init__(self):
                self.id = 10
                self.guild_xid = 1
                self.channel_xid = 2
                self.message_xid = 3
                self.users = [FakeUser()]
                self.tags = []

            def is_expired(self):
                return True

        fake_game = FakeGame()

        def buggy_expired(session):
            return [fake_game]

        monkeypatch.setattr(Game, "expired", buggy_expired)
        monkeypatch.setattr(Session, "delete", Mock())

        await cleanup_expired_games(client)

        assert fake_game.users[0].game_id == 11
        assert user_has_game(client, GUY)

    async def test_game_cleanup_expired_buggy_list(
        self, client, channel_maker, monkeypatch
    ):
        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))

        def buggy_expired(session):
            # Return all games even if they're not expired
            return session.query(Game).all()

        monkeypatch.setattr(Game, "expired", buggy_expired)

        assert user_has_game(client, GUY)
        await cleanup_expired_games(client)
        assert user_has_game(client, GUY)  # Check that the user's game still exists

    async def test_game_cleanup_expired_buggy_game(self, client, monkeypatch):
        def buggy_expired(session):
            # Return a weird buggy game that's missing some reqired information for
            # being cleaned up by this task, but is theoretically valid in terms of
            # database constraints.
            now = datetime.utcnow()
            server = Server(guild_xid=42)
            session.add(Game(expires_at=now, status="pending", size=4, server=server))
            session.commit()
            return session.query(Game).all()

        mock_try_to_delete_message = AsyncMock()

        monkeypatch.setattr(Game, "expired", buggy_expired)
        monkeypatch.setattr(client, "try_to_delete_message", mock_try_to_delete_message)
        await cleanup_expired_games(client)
        mock_try_to_delete_message.assert_not_called()

    async def test_game_cleanup_expired_after_left(self, client, freezer, channel_maker):
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)

        channel = channel_maker.text()
        await client.on_message(MockMessage(GUY, channel, "!lfg"))
        post = channel.last_sent_message
        assert channel.last_sent_embed == game_embed_for(client, GUY, False)

        assert user_has_game(client, GUY)

        client.mock_disconnect_user(GUY)

        freezer.move_to(NOW + timedelta(days=3))
        await cleanup_expired_games(client)

        assert not user_has_game(client, GUY)
        assert len(GUY.all_sent_calls) == 0

        # post.delete.assert_called()
        assert post.last_edited_call == {
            "args": ("Sorry, this game was expired due to inactivity.",),
            "kwargs": {},
        }

    # async def test_cleanup_voice_channels(
    #     self, client, channel_maker, monkeypatch, freezer
    # ):
    #     NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
    #     freezer.move_to(NOW)

    #     channel = channel_maker.text()
    #     author = an_admin()
    #     await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

    #     await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
    #     await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
    #     assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] == 1

    #     mock_voice_channel = channel_maker.voice("whatever", [])
    #     mock_get_channel = Mock(return_value=mock_voice_channel)
    #     monkeypatch.setattr(client, "get_channel", mock_get_channel)

    #     await cleanup_old_voice_channels(client)
    #     mock_voice_channel.delete.assert_not_called()

    #     freezer.move_to(NOW + timedelta(days=3))
    #     await cleanup_old_voice_channels(client)
    #     mock_voice_channel.delete.assert_called()
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] is None

    # async def test_cleanup_voice_channels_old_but_occupied(
    #     self, client, channel_maker, monkeypatch, freezer
    # ):
    #     NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
    #     freezer.move_to(NOW)

    #     channel = channel_maker.text()
    #     author = an_admin()
    #     await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

    #     await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
    #     await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
    #     assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] == 1

    #     # simulate JACOB sitting in the voice channel for way too long
    #     mock_voice_channel = channel_maker.voice("whatever", [JACOB])
    #     mock_get_channel = Mock(return_value=mock_voice_channel)
    #     monkeypatch.setattr(client, "get_channel", mock_get_channel)
    #     freezer.move_to(NOW + timedelta(days=3))

    #     await cleanup_old_voice_channels(client)
    #     mock_voice_channel.delete.assert_called()
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] is None

    # async def test_cleanup_voice_channels_error_fetch_channel(
    #     self, client, channel_maker, monkeypatch, freezer
    # ):
    #     NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
    #     freezer.move_to(NOW)

    #     channel = channel_maker.text()
    #     author = an_admin()
    #     await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

    #     await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
    #     await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
    #     assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] == 1

    #     mock_get_channel = Mock(return_value=None)
    #     mock_fetch_channel = AsyncMock(return_value=None)
    #     monkeypatch.setattr(client, "get_channel", mock_get_channel)
    #     monkeypatch.setattr(client, "fetch_channel", mock_fetch_channel)

    #     freezer.move_to(NOW + timedelta(days=3))
    #     await cleanup_old_voice_channels(client)

    #     mock_get_channel.assert_called()
    #     mock_fetch_channel.assert_called()
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] is None

    # async def test_cleanup_old_voice_channels_error_delete_channel(
    #     self, client, channel_maker, monkeypatch, freezer, caplog
    # ):
    #     caplog.set_level(logging.INFO)
    #     NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
    #     freezer.move_to(NOW)
    #     channel = channel_maker.text()
    #     author = an_admin()
    #     await client.on_message(MockMessage(author, channel, "!spellbot voice on"))
    #     await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
    #     await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
    #     mock_voice_channel = channel_maker.voice("whatever", [])
    #     mock_get_channel = Mock(return_value=mock_voice_channel)
    #     monkeypatch.setattr(client, "get_channel", mock_get_channel)
    #     freezer.move_to(NOW + timedelta(days=3))
    #     mock_safe_delete_channel = AsyncMock(return_value=None)
    #     monkeypatch.setattr(tasks, "safe_delete_channel", mock_safe_delete_channel)

    #     await cleanup_old_voice_channels(client)

    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     game_id = game_json_for_amy["id"]
    #     assert f"failed to delete voice channel for game {game_id}" in caplog.text

    # async def test_cleanup_voice_channels_in_use(
    #     self, client, channel_maker, monkeypatch, freezer
    # ):
    #     NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
    #     freezer.move_to(NOW)

    #     channel = channel_maker.text()
    #     author = an_admin()
    #     await client.on_message(MockMessage(author, channel, "!spellbot voice on"))

    #     await client.on_message(MockMessage(JACOB, channel, "!lfg ~legacy"))
    #     await client.on_message(MockMessage(AMY, channel, "!lfg ~legacy"))
    #     assert game_embed_for(client, AMY, True) == game_embed_for(client, JACOB, True)
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] == 1

    #     mock_voice_channel = channel_maker.voice("whatever", [AMY, JACOB])
    #     mock_get_channel = Mock(return_value=mock_voice_channel)
    #     monkeypatch.setattr(client, "get_channel", mock_get_channel)

    #     freezer.move_to(NOW + timedelta(hours=REALLY_OLD_GAMES_HOURS - 1))
    #     await cleanup_old_voice_channels(client)

    #     mock_voice_channel.delete.assert_not_called()
    #     game_json_for_amy = game_json_for(client, AMY)
    #     assert game_json_for_amy
    #     assert game_json_for_amy["voice_channel_xid"] == 1

    async def test_update_metrics_with_data(
        self, client, channel_maker, monkeypatch, freezer
    ):
        channel = channel_maker.text()
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        metrics = MagicMock()
        monkeypatch.setattr(client, "metrics_db", metrics)
        for day in range(7):
            freezer.move_to(NOW + timedelta(days=day))
            for _ in range(day + 1):
                await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
                await client.on_message(MockMessage(JACOB, channel, "!lfg size:2"))

        await update_metrics(client)

        metrics.mset.assert_called_with(
            {
                "games_0": 7,
                "games_1": 6,
                "games_2": 5,
                "games_3": 4,
                "games_4": 3,
                "games_5": 2,
                "servers_0": 1,
                "users_0": 2,
            }
        )

    async def test_update_metrics_without_data(self, client, monkeypatch):
        metrics = MagicMock()
        monkeypatch.setattr(client, "metrics_db", metrics)

        await update_metrics(client)

        metrics.mset.assert_called_with(
            {"games": 0, "servers": 0, "users": 0, "active": 1}
        )

    async def test_update_metrics_redis_error(self, client, monkeypatch, caplog):
        metrics = Mock()
        metrics.mset = Mock(side_effect=redis.exceptions.RedisError("network error"))
        monkeypatch.setattr(client, "metrics_db", metrics)

        await update_metrics(client)

        assert "redis.exceptions.RedisError: network error" in caplog.text

    async def test_update_average_wait_times(self, client, channel_maker, freezer):
        channel = channel_maker.text()
        NOW = datetime(year=1982, month=4, day=24, tzinfo=pytz.utc)
        freezer.move_to(NOW)
        await client.on_message(MockMessage(AMY, channel, "!lfg size:2"))
        freezer.move_to(NOW + timedelta(minutes=10))
        await client.on_message(MockMessage(JACOB, channel, "!lfg size:2"))

        await update_average_wait_times(client)

        assert client.average_wait_times["500-6500"] == pytest.approx(10)

    async def test_begin_background_tasks(self, client, monkeypatch):
        mock_task = AsyncMock()

        monkeypatch.setattr(
            tasks, "BACKROUND_TASK_SPECS", [{"interval": 200, "function": mock_task}]
        )
        jobs = begin_background_tasks(client)

        while not mock_task.called:
            await asyncio.sleep(1)

        for job in jobs:
            job.cancel()

    async def test_begin_background_tasks_failure(self, client, monkeypatch, caplog):
        caplog.set_level(logging.INFO)
        mock_task = AsyncMock()
        mock_task.side_effect = RuntimeError("mock exception")

        monkeypatch.setattr(
            tasks, "BACKROUND_TASK_SPECS", [{"interval": 200, "function": mock_task}]
        )
        jobs = begin_background_tasks(client)

        while not mock_task.called:
            await asyncio.sleep(1)

        for job in jobs:
            job.cancel()

        assert "unhandled exception in task" in caplog.text
        assert "mock exception" in caplog.text
