from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from spellbot.cogs import BlockCog
from spellbot.database import DatabaseSession
from spellbot.models import Block, User
from tests.fixtures import run_command

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
        settings: Settings,
    ) -> None:
        target = MagicMock()
        target.id = 2
        target.display_name = "target-author-display-name"

        cta = (
            "You can view and manage your blocked users from your profile page.\n\n"
            f"[Open your profile on spellbot.io]({settings.API_BASE_URL}/u/{interaction.user.id})"
        )

        await run_command(cog.block, interaction, target=target)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"<@{target.id}> has been blocked.\n\n{cta}",
            ephemeral=True,
        )

        target_user = (
            await DatabaseSession.execute(select(User).where(User.xid == target.id))
        ).scalar_one()
        assert target_user.name == target.display_name
        assert target_user.xid == target.id

        action_user = (
            await DatabaseSession.execute(select(User).where(User.xid == interaction.user.id))
        ).scalar_one()
        assert action_user.name == interaction.user.display_name
        assert action_user.xid == interaction.user.id

        block = (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.user_xid == interaction.user.id,
                    Block.blocked_user_xid == target.id,
                ),
            )
        ).scalar_one()
        assert block.user_xid == interaction.user.id
        assert block.blocked_user_xid == target.id

        DatabaseSession.expire_all()
        interaction.response.send_message.reset_mock()  # type: ignore
        await run_command(cog.unblock, interaction, target=target)
        interaction.response.send_message.assert_called_once_with(  # type: ignore
            f"<@{target.id}> has been unblocked.\n\n{cta}",
            ephemeral=True,
        )
        block = (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.user_xid == interaction.user.id,
                    Block.blocked_user_xid == target.id,
                ),
            )
        ).scalar_one_or_none()
        assert block is None

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
        blocks = list((await DatabaseSession.execute(select(Block))).scalars().all())
        assert len(blocks) == 0

    async def test_blocked_links_to_profile(
        self,
        cog: BlockCog,
        user: User,
        interaction: discord.Interaction,
        settings: Settings,
    ) -> None:
        await run_command(cog.blocked, interaction)

        link = f"{settings.API_BASE_URL}/u/{interaction.user.id}"
        interaction.response.send_message.assert_called_once_with(  # type: ignore
            (
                "You can view and manage your blocked users from your profile page.\n\n"
                f"[Open your profile on spellbot.io]({link})"
            ),
            ephemeral=True,
        )
