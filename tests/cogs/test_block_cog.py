from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock, patch

import pytest
import pytest_asyncio

from spellbot.cogs import BlockCog
from spellbot.database import DatabaseSession
from spellbot.models import Block, User
from tests.fixtures import Factories, get_last_send_message, run_command

if TYPE_CHECKING:
    import discord

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> BlockCog:
    return BlockCog(bot)


@pytest.mark.asyncio
class TestCogBlock:
    async def test_block_and_unblock(
        self,
        cog: BlockCog,
        interaction: discord.Interaction,
    ) -> None:
        target = MagicMock()
        target.id = 2
        target.display_name = "target-author-display-name"

        await run_command(cog.block, interaction, target=target)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"<@{target.id}> has been blocked.",
            ephemeral=True,
        )

        users = sorted(DatabaseSession.query(User).all(), key=lambda u: u.name)
        assert len(users) == 2
        assert users[0].name == target.display_name
        assert users[0].xid == target.id
        assert users[1].name == interaction.user.display_name
        assert users[1].xid == interaction.user.id

        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 1
        assert blocks[0].user_xid == interaction.user.id
        assert blocks[0].blocked_user_xid == target.id

        DatabaseSession.expire_all()
        interaction.response.send_message.reset_mock()  # type: ignore
        await run_command(cog.unblock, interaction, target=target)
        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 0

    async def test_block_self(
        self,
        cog: BlockCog,
        interaction: discord.Interaction,
    ) -> None:
        target = MagicMock()
        target.id = interaction.user.id
        target.display_name = interaction.user.display_name

        await run_command(cog.block, interaction, target=target)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            "You can not block yourself.",
            ephemeral=True,
        )
        blocks = list(DatabaseSession.query(Block).all())
        assert len(blocks) == 0

    async def test_blocked_happy_path(
        self,
        cog: BlockCog,
        user: User,
        interaction: discord.Interaction,
        factories: Factories,
        settings: Settings,
    ) -> None:
        target = factories.user.create()
        factories.block.create(user_xid=user.xid, blocked_user_xid=target.xid)

        await run_command(cog.blocked, interaction)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            embed=ANY,
            ephemeral=True,
        )
        assert get_last_send_message(interaction, "embed") == {
            "color": settings.INFO_EMBED_COLOR,
            "description": f"<@{target.xid}> ({target.name})\n",
            "thumbnail": {"url": settings.ICO_URL},
            "title": "Blocked Users",
            "type": "rich",
            "footer": {"text": "Page 1 of 1"},
            "flags": 0,
        }

    async def test_blocked_no_one(
        self,
        cog: BlockCog,
        user: User,
        interaction: discord.Interaction,
        settings: Settings,
    ) -> None:
        await run_command(cog.blocked, interaction)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            embed=ANY,
            ephemeral=True,
        )
        assert get_last_send_message(interaction, "embed") == {
            "color": settings.INFO_EMBED_COLOR,
            "description": "You have no blocked users.",
            "thumbnail": {"url": settings.ICO_URL},
            "title": "Blocked Users",
            "type": "rich",
            "flags": 0,
        }

    async def test_blocked_pagination(
        self,
        cog: BlockCog,
        user: User,
        interaction: discord.Interaction,
        factories: Factories,
        settings: Settings,
    ) -> None:
        target1 = factories.user.create(xid=8001, name="alice")
        target2 = factories.user.create(xid=8002, name="bob")
        factories.block.create(user_xid=user.xid, blocked_user_xid=target1.xid)
        factories.block.create(user_xid=user.xid, blocked_user_xid=target2.xid)

        with patch("spellbot.actions.block_action.EMBED_DESCRIPTION_SIZE_LIMIT", 20):
            await run_command(cog.blocked, interaction)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            embed=ANY,
            ephemeral=True,
        )
        assert get_last_send_message(interaction, "embed") == {
            "color": settings.INFO_EMBED_COLOR,
            "description": f"<@{target1.xid}> ({target1.name})\n",
            "thumbnail": {"url": settings.ICO_URL},
            "title": "Blocked Users",
            "type": "rich",
            "footer": {"text": "Page 1 of 2"},
            "flags": 0,
        }

        interaction.response.send_message.reset_mock()  # type: ignore

        with patch("spellbot.actions.block_action.EMBED_DESCRIPTION_SIZE_LIMIT", 20):
            await run_command(cog.blocked, interaction, page=2)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            embed=ANY,
            ephemeral=True,
        )
        assert get_last_send_message(interaction, "embed") == {
            "color": settings.INFO_EMBED_COLOR,
            "description": f"<@{target2.xid}> ({target2.name})\n",
            "thumbnail": {"url": settings.ICO_URL},
            "title": "Blocked Users",
            "type": "rich",
            "footer": {"text": "Page 2 of 2"},
            "flags": 0,
        }
