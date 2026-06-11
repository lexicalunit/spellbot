from __future__ import annotations

from spellbot.models import (
    WEB_EDITABLE,
    Channel,
    Guild,
    web_editable,
    web_editable_columns,
    web_editable_docs,
)


class TestWebEditable:
    def test_web_editable_appends_marker(self) -> None:
        assert web_editable("Some help.") == f"Some help. {WEB_EDITABLE}"

    def test_columns_match_marked_docs(self) -> None:
        guild_cols = web_editable_columns(Guild)
        assert guild_cols == {
            "motd",
            "show_links",
            "voice_create",
            "use_max_bitrate",
            "suggest_voice_category",
            "enable_mythic_track",
        }
        # Owner-only / internal columns are never marked editable.
        assert "banned" not in guild_cols
        assert "promote" not in guild_cols

    def test_docs_strip_marker_and_cover_all_columns(self) -> None:
        docs = web_editable_docs(Channel)
        assert docs.keys() == web_editable_columns(Channel)
        for help_text in docs.values():
            assert WEB_EDITABLE not in help_text
            assert help_text  # non-empty help for every editable column
            assert not help_text.endswith(" ")
        assert docs["default_bracket"] == "The default commander bracket for this channel"
