from __future__ import annotations

from datetime import UTC, datetime

from spellbot.branding import (
    GUILD_THEME_OVERRIDES,
    PRIDE_GUILDS,
    THEME_CONFIGS,
    Theme,
    get_theme,
    get_thumb_url,
    is_autism_awareness,
    is_black_history,
    is_pride,
    is_trans,
)


class TestThemeMatchers:
    def test_is_pride_in_june(self) -> None:
        june = datetime(2024, 6, 15, tzinfo=UTC)
        assert is_pride(None, june) is True
        assert is_pride(12345, june) is True

    def test_is_pride_outside_june_for_regular_guild(self) -> None:
        march = datetime(2024, 3, 15, tzinfo=UTC)
        assert is_pride(12345, march) is False
        assert is_pride(None, march) is False

    def test_is_pride_year_round_for_pride_guilds(self) -> None:
        march = datetime(2024, 3, 15, tzinfo=UTC)
        for guild_xid in PRIDE_GUILDS:
            assert is_pride(guild_xid, march) is True

    def test_is_black_history_in_february(self) -> None:
        february = datetime(2024, 2, 15, tzinfo=UTC)
        assert is_black_history(None, february) is True
        assert is_black_history(12345, february) is True

    def test_is_black_history_outside_february(self) -> None:
        march = datetime(2024, 3, 15, tzinfo=UTC)
        assert is_black_history(None, march) is False

    def test_is_trans_in_november(self) -> None:
        november = datetime(2024, 11, 15, tzinfo=UTC)
        assert is_trans(None, november) is True
        assert is_trans(12345, november) is True

    def test_is_trans_on_march_31(self) -> None:
        tdov = datetime(2024, 3, 31, tzinfo=UTC)
        assert is_trans(None, tdov) is True

    def test_is_trans_on_march_30(self) -> None:
        march_30 = datetime(2024, 3, 30, tzinfo=UTC)
        assert is_trans(None, march_30) is False

    def test_is_trans_outside_november_and_march_31(self) -> None:
        june = datetime(2024, 6, 15, tzinfo=UTC)
        assert is_trans(None, june) is False

    def test_is_autism_awareness_on_april_2(self) -> None:
        april_2 = datetime(2024, 4, 2, tzinfo=UTC)
        assert is_autism_awareness(None, april_2) is True
        assert is_autism_awareness(12345, april_2) is True

    def test_is_autism_awareness_on_april_1(self) -> None:
        april_1 = datetime(2024, 4, 1, tzinfo=UTC)
        assert is_autism_awareness(None, april_1) is False

    def test_is_autism_awareness_on_april_3(self) -> None:
        april_3 = datetime(2024, 4, 3, tzinfo=UTC)
        assert is_autism_awareness(None, april_3) is False


class TestGetTheme:
    def test_default_theme_on_regular_day(self) -> None:
        july = datetime(2024, 7, 15, tzinfo=UTC)
        assert get_theme(12345, july) == Theme.DEFAULT

    def test_default_theme_with_none_guild(self) -> None:
        july = datetime(2024, 7, 15, tzinfo=UTC)
        assert get_theme(None, july) == Theme.DEFAULT

    def test_convoke_guild_override(self) -> None:
        # Convoke guild should always get Convoke theme, even during Pride Month
        convoke_guild = next(iter(GUILD_THEME_OVERRIDES.keys()))
        june = datetime(2024, 6, 15, tzinfo=UTC)
        assert get_theme(convoke_guild, june) == Theme.CONVOKE

    def test_pride_theme_in_june(self) -> None:
        june = datetime(2024, 6, 15, tzinfo=UTC)
        assert get_theme(12345, june) == Theme.PRIDE

    def test_black_history_theme_in_february(self) -> None:
        february = datetime(2024, 2, 15, tzinfo=UTC)
        assert get_theme(12345, february) == Theme.BLACK_HISTORY

    def test_trans_theme_in_november(self) -> None:
        november = datetime(2024, 11, 15, tzinfo=UTC)
        assert get_theme(12345, november) == Theme.TRANS

    def test_trans_theme_on_march_31(self) -> None:
        tdov = datetime(2024, 3, 31, tzinfo=UTC)
        assert get_theme(12345, tdov) == Theme.TRANS

    def test_autism_theme_on_april_2(self) -> None:
        april_2 = datetime(2024, 4, 2, tzinfo=UTC)
        assert get_theme(12345, april_2) == Theme.AUTISM

    def test_pride_guild_year_round(self) -> None:
        pride_guild = next(iter(PRIDE_GUILDS))
        march = datetime(2024, 3, 15, tzinfo=UTC)
        assert get_theme(pride_guild, march) == Theme.PRIDE

    def test_defaults_to_utc_now_when_no_time_provided(self) -> None:
        # Just verify it doesn't crash - actual theme depends on current date
        theme = get_theme(12345)
        assert theme in Theme


class TestGetThumbUrl:
    def test_returns_default_thumb_url(self) -> None:
        july = datetime(2024, 7, 15, tzinfo=UTC)
        url = get_thumb_url(12345, july)
        assert url == THEME_CONFIGS[Theme.DEFAULT].thumb_url

    def test_returns_pride_thumb_url_in_june(self) -> None:
        june = datetime(2024, 6, 15, tzinfo=UTC)
        url = get_thumb_url(12345, june)
        assert url == THEME_CONFIGS[Theme.PRIDE].thumb_url

    def test_returns_convoke_thumb_url_for_convoke_guild(self) -> None:
        convoke_guild = next(iter(GUILD_THEME_OVERRIDES.keys()))
        url = get_thumb_url(convoke_guild)
        assert url == THEME_CONFIGS[Theme.CONVOKE].thumb_url

    def test_all_themes_have_configs(self) -> None:
        for theme in Theme:
            assert theme in THEME_CONFIGS
            assert THEME_CONFIGS[theme].thumb_url.startswith("http")
