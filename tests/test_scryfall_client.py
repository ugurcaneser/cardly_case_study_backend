from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.scryfall_client import ScryfallError, search_by_name, search_by_name_and_number

_SAMPLE_CARD = {
    "id": "abc-123",
    "name": "Lightning Bolt",
    "set_name": "Masters 25",
    "set": "a25",
    "collector_number": "133",
    "rarity": "common",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "image_uris": {"normal": "https://example.com/card.jpg"},
    "prices": {"usd": "0.25", "eur": "0.20"},
}


def _mock_response(status_code: int, json_body: dict | None = None, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.text = text
    return response


class TestSearchByName:
    def test_returns_a_parsed_card_on_a_successful_match(self):
        with patch("app.services.scryfall_client.httpx.get", return_value=_mock_response(200, _SAMPLE_CARD)):
            card = search_by_name("Lightning Bolt")

        assert card is not None
        assert card.scryfall_id == "abc-123"
        assert card.name == "Lightning Bolt"
        assert card.set_name == "Masters 25"
        assert card.set_code == "a25"
        assert card.collector_number == "133"
        assert card.rarity == "common"
        assert card.mana_cost == "{R}"
        assert card.type_line == "Instant"
        assert card.oracle_text == "Lightning Bolt deals 3 damage to any target."
        assert card.image_url == "https://example.com/card.jpg"
        assert card.prices == {"usd": "0.25", "eur": "0.20"}

    def test_returns_none_on_a_404_no_match(self):
        with patch("app.services.scryfall_client.httpx.get", return_value=_mock_response(404)):
            assert search_by_name("Not A Real Card Name") is None

    def test_raises_on_an_unexpected_status_code(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(500, text="internal error"),
        ):
            with pytest.raises(ScryfallError, match="status 500"):
                search_by_name("Lightning Bolt")

    def test_wraps_a_network_failure(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(ScryfallError, match="request failed"):
                search_by_name("Lightning Bolt")

    def test_raises_on_a_malformed_response_missing_required_fields(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(200, {"id": "abc-123"}),
        ):
            with pytest.raises(ScryfallError, match="Unexpected Scryfall response shape"):
                search_by_name("Lightning Bolt")

    def test_handles_a_card_with_no_image_uris_gracefully(self):
        card_without_image = {**_SAMPLE_CARD, "image_uris": None}
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(200, card_without_image),
        ):
            card = search_by_name("Lightning Bolt")

        assert card is not None
        assert card.image_url is None

    def test_defaults_prices_to_an_empty_dict_when_missing(self):
        card_without_prices = {**_SAMPLE_CARD, "prices": None}
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(200, card_without_prices),
        ):
            card = search_by_name("Lightning Bolt")

        assert card is not None
        assert card.prices == {}


class TestSearchByNameAndNumber:
    def test_returns_the_first_matching_printing(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(200, {"data": [_SAMPLE_CARD]}),
        ):
            card = search_by_name_and_number("Lightning Bolt", "133")

        assert card is not None
        assert card.set_code == "a25"
        assert card.collector_number == "133"

    def test_returns_none_on_a_404_no_match(self):
        with patch("app.services.scryfall_client.httpx.get", return_value=_mock_response(404)):
            assert search_by_name_and_number("Lightning Bolt", "999") is None

    def test_returns_none_when_the_data_array_is_empty(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(200, {"data": []}),
        ):
            assert search_by_name_and_number("Lightning Bolt", "999") is None

    def test_raises_on_an_unexpected_status_code(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            return_value=_mock_response(500, text="internal error"),
        ):
            with pytest.raises(ScryfallError, match="status 500"):
                search_by_name_and_number("Lightning Bolt", "133")

    def test_wraps_a_network_failure(self):
        with patch(
            "app.services.scryfall_client.httpx.get",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(ScryfallError, match="request failed"):
                search_by_name_and_number("Lightning Bolt", "133")
