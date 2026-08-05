from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot import services
from spellbot.database import DatabaseSession
from spellbot.models import WebAction, WebActionKind, WebActionStatus

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


async def make_channel(factories: Factories) -> tuple[int, int, int]:
    """Create a guild, channel, and user, returning their external ids."""
    guild = factories.guild.create(xid=910001)
    channel = factories.channel.create(xid=910002, guild=guild)
    user = factories.user.create(xid=910003)
    return guild.xid, channel.xid, user.xid


@pytest.mark.asyncio
class TestWebActionsService:
    async def test_enqueue_starts_pending(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        action = await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="fr",
            params={"format": 1},
        )
        assert action.status == WebActionStatus.PENDING.value
        assert action.locale == "fr"
        assert action.params == {"format": 1}
        assert action.notices == []
        assert action.resolved_at is None

    async def test_get_is_scoped_to_the_requesting_user(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        other = factories.user.create(xid=910004)
        action = await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        assert await services.web_actions.get(action.id, user_xid=user_xid) is not None
        # Another user must not be able to read this row, or the status endpoint
        # becomes an enumeration oracle over everyone's requests.
        assert await services.web_actions.get(action.id, user_xid=other.xid) is None

    async def test_claim_marks_running_and_is_not_repeatable(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        claimed = await services.web_actions.claim([guild_xid])
        assert len(claimed) == 1
        assert claimed[0].status == WebActionStatus.RUNNING.value
        # A second poll must not hand the same request to another worker.
        assert await services.web_actions.claim([guild_xid]) == []

    async def test_claim_skips_other_guilds(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        # A shard that is not in this guild can not act on the request.
        assert await services.web_actions.claim([999999]) == []

    async def test_claim_with_no_guilds_does_nothing(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        assert await services.web_actions.claim([]) == []

    async def test_claim_respects_the_limit(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        for _ in range(3):
            await services.web_actions.enqueue(
                user_xid=user_xid,
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                kind=WebActionKind.CREATE.value,
                locale="en",
            )
        assert len(await services.web_actions.claim([guild_xid], limit=2)) == 2

    async def test_resolve_success(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        action = await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        await services.web_actions.resolve(action.id, notices=["all set"])
        DatabaseSession.expire_all()
        found = await services.web_actions.get(action.id, user_xid=user_xid)
        assert found is not None
        assert found.status == WebActionStatus.DONE.value
        assert found.error_code is None
        assert found.notices == ["all set"]
        assert found.resolved_at is not None

    async def test_resolve_failure_records_the_code(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        action = await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.JOIN.value,
            locale="en",
        )
        await services.web_actions.resolve(action.id, error_code="not_a_member")
        DatabaseSession.expire_all()
        found = await services.web_actions.get(action.id, user_xid=user_xid)
        assert found is not None
        assert found.status == WebActionStatus.ERROR.value
        assert found.error_code == "not_a_member"

    async def test_expire_stale_fails_old_unfinished_actions(self, factories: Factories) -> None:
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        old = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(hours=1)
        stale = factories.web_action.create(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            status=WebActionStatus.PENDING.value,
            locale="en",
            params={},
            notices=[],
            created_at=old,
            updated_at=old,
        )
        fresh = await services.web_actions.enqueue(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.CREATE.value,
            locale="en",
        )
        assert await services.web_actions.expire_stale(timedelta(minutes=5), "expired") == 1
        DatabaseSession.expire_all()
        expired = await services.web_actions.get(stale.id, user_xid=user_xid)
        assert expired is not None
        assert expired.status == WebActionStatus.ERROR.value
        assert expired.error_code == "expired"
        # The request made a moment ago must be left alone for the worker to pick up.
        still_pending = await services.web_actions.get(fresh.id, user_xid=user_xid)
        assert still_pending is not None
        assert still_pending.status == WebActionStatus.PENDING.value

    async def test_expire_stale_sweeps_abandoned_claims(self, factories: Factories) -> None:
        # A worker that crashed mid-action leaves a `running` row nobody will resolve.
        guild_xid, channel_xid, user_xid = await make_channel(factories)
        old = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(hours=1)
        stuck = factories.web_action.create(
            user_xid=user_xid,
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            kind=WebActionKind.JOIN.value,
            status=WebActionStatus.RUNNING.value,
            locale="en",
            params={},
            notices=[],
            created_at=old,
            updated_at=old,
        )
        assert await services.web_actions.expire_stale(timedelta(minutes=5), "expired") == 1
        DatabaseSession.expire_all()
        found = await DatabaseSession.get(WebAction, stuck.id)
        assert found is not None
        assert found.status == WebActionStatus.ERROR.value
