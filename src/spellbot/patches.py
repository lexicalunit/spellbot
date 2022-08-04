from __future__ import annotations

from discord.abc import _Overwrites


def patch_discord_overwrites() -> None:  # pragma: no cover
    """
    Patches the default `is_role()` and `is_member()` in discord.py to work around a bug:
    For more details see: https://github.com/Rapptz/discord.py/issues/8299
    """

    def _Overwrites_is_role(self: _Overwrites) -> bool:
        return self.type == _Overwrites.ROLE or str(self.type) == "role"

    def _Overwrites_is_member(self: _Overwrites) -> bool:
        return self.type == _Overwrites.MEMBER or str(self.type) == "member"

    _Overwrites.is_role = _Overwrites_is_role
    _Overwrites.is_member = _Overwrites_is_member
