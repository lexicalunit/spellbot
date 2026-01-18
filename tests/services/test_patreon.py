from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spellbot.services.patreon import (
    PatreonService,
    get_patreon_campaign_url,
    get_patron_ids,
    get_supporters,
)


class TestGetPatreonCampaignUrl:
    def test_returns_valid_url(self) -> None:
        with patch("spellbot.services.patreon.settings") as mock_settings:
            mock_settings.PATREON_CAMPAIGN = "12345"
            url = get_patreon_campaign_url()

        assert "https://www.patreon.com/api/oauth2/v2/campaigns/12345/members" in url
        assert "fields%5Bmember%5D=patron_status" in url
        assert "fields%5Buser%5D=social_connections" in url
        assert "include=user" in url


class TestGetPatronIds:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            pytest.param({}, set(), id="empty_data"),
            pytest.param({"other": "stuff"}, set(), id="no_data_key"),
            pytest.param({"data": []}, set(), id="empty_data_list"),
            pytest.param(
                {"data": [{"id": "123", "type": "member"}]},
                set(),
                id="no_attributes",
            ),
            pytest.param(
                {"data": [{"id": "123", "attributes": {}}]},
                set(),
                id="no_patron_status",
            ),
            pytest.param(
                {"data": [{"id": "123", "attributes": {"some_other_field": "value"}}]},
                set(),
                id="attributes_without_patron_status",
            ),
            pytest.param(
                {"data": [{"id": "123", "attributes": {"patron_status": "former_patron"}}]},
                set(),
                id="not_active",
            ),
            pytest.param(
                {"data": [{"id": "123", "attributes": {"patron_status": "active_patron"}}]},
                set(),
                id="no_relationships",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "123",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {},
                        },
                    ],
                },
                set(),
                id="no_user_relationship",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "123",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {}},
                        },
                    ],
                },
                set(),
                id="no_user_data",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "123",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {"data": {}}},
                        },
                    ],
                },
                set(),
                id="no_user_id",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "123",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {"data": {"type": "user"}}},
                        },
                    ],
                },
                set(),
                id="user_data_without_id",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "123",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {"data": {"id": "user123"}}},
                        },
                    ],
                },
                {"user123"},
                id="valid_active_patron",
            ),
            pytest.param(
                {
                    "data": [
                        {
                            "id": "1",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {"data": {"id": "user1"}}},
                        },
                        {
                            "id": "2",
                            "attributes": {"patron_status": "former_patron"},
                            "relationships": {"user": {"data": {"id": "user2"}}},
                        },
                        {
                            "id": "3",
                            "attributes": {"patron_status": "active_patron"},
                            "relationships": {"user": {"data": {"id": "user3"}}},
                        },
                    ],
                },
                {"user1", "user3"},
                id="multiple_patrons",
            ),
        ],
    )
    def test_get_patron_ids(self, data: dict[str, Any], expected: set[str]) -> None:
        assert get_patron_ids(data) == expected


TEST_ACCOUNT = 711717544435646494


class TestGetSupporters:
    @pytest.mark.parametrize(
        ("data", "patron_ids", "expected"),
        [
            pytest.param({}, set(), {TEST_ACCOUNT}, id="empty_data"),
            pytest.param({"other": "data"}, {"patron1"}, {TEST_ACCOUNT}, id="no_included"),
            pytest.param(
                {"included": [{"id": "other_user", "attributes": {}}]},
                {"patron1"},
                {TEST_ACCOUNT},
                id="no_matching_patron",
            ),
            pytest.param(
                {"included": [{"id": "patron1", "attributes": {"social_connections": {}}}]},
                {"patron1"},
                {TEST_ACCOUNT},
                id="no_discord_connection",
            ),
            pytest.param(
                {
                    "included": [
                        {
                            "id": "patron1",
                            "attributes": {
                                "social_connections": {"discord": {"user_id": "123456789"}},
                            },
                        },
                    ],
                },
                {"patron1"},
                {123456789, TEST_ACCOUNT},
                id="with_discord_connection",
            ),
            pytest.param(
                {
                    "included": [
                        {"attributes": {"social_connections": {"discord": {"user_id": "123"}}}},
                    ],
                },
                {"patron1"},
                {TEST_ACCOUNT},
                id="item_without_id",
            ),
            pytest.param(
                {
                    "included": [
                        {
                            "id": "patron1",
                            "attributes": {
                                "social_connections": {"discord": {"user_id": "111"}},
                            },
                        },
                        {
                            "id": "patron2",
                            "attributes": {
                                "social_connections": {"discord": {"user_id": "222"}},
                            },
                        },
                    ],
                },
                {"patron1", "patron2"},
                {111, 222, TEST_ACCOUNT},
                id="multiple_patrons",
            ),
        ],
    )
    def test_get_supporters(
        self,
        data: dict[str, Any],
        patron_ids: set[str],
        expected: set[int],
    ) -> None:
        result = get_supporters(data, patron_ids)
        assert result == expected


@pytest.mark.asyncio
class TestPatreonService:
    async def test_supporters_returns_empty_in_pytest(self) -> None:
        """In pytest, supporters() returns empty set due to running_in_pytest() check."""
        service = PatreonService()
        result = await service.supporters()
        assert result == set()

    async def test_supporters_with_mocked_http_success(self) -> None:
        """Test successful HTTP response with pagination."""
        page1_data = {
            "data": [
                {
                    "id": "member1",
                    "attributes": {"patron_status": "active_patron"},
                    "relationships": {"user": {"data": {"id": "user1"}}},
                },
            ],
            "included": [
                {
                    "id": "user1",
                    "attributes": {
                        "social_connections": {"discord": {"user_id": "123456"}},
                    },
                },
            ],
            "links": {"next": "https://patreon.com/page2"},
        }
        page2_data = {
            "data": [
                {
                    "id": "member2",
                    "attributes": {"patron_status": "active_patron"},
                    "relationships": {"user": {"data": {"id": "user2"}}},
                },
            ],
            "included": [
                {
                    "id": "user2",
                    "attributes": {
                        "social_connections": {"discord": {"user_id": "789012"}},
                    },
                },
            ],
            "links": {},
        }

        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = page1_data

        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = page2_data

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_response1, mock_response2]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch("spellbot.services.patreon.running_in_pytest", return_value=False),
            patch("spellbot.services.patreon.httpx.Client", return_value=mock_client),
        ):
            service = PatreonService()
            result = await service.supporters()

        assert 123456 in result
        assert 789012 in result
        assert 711717544435646494 in result  # test account

    async def test_supporters_with_http_error(self) -> None:
        """Test HTTP error response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch("spellbot.services.patreon.running_in_pytest", return_value=False),
            patch("spellbot.services.patreon.httpx.Client", return_value=mock_client),
        ):
            service = PatreonService()
            result = await service.supporters()

        # Should still return test account even on error
        assert 711717544435646494 in result

    async def test_supporters_with_exception(self) -> None:
        """Test exception during HTTP request."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch("spellbot.services.patreon.running_in_pytest", return_value=False),
            patch("spellbot.services.patreon.httpx.Client", return_value=mock_client),
        ):
            service = PatreonService()
            result = await service.supporters()

        # Should return empty set on exception
        assert result == set()
