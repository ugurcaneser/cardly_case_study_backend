from unittest.mock import patch

import pytest

from app.services.enrichment_service import (
    ErrorEnrichment,
    MatchedEnrichment,
    UnrecognizedEnrichment,
    enrich_image,
)
from app.services.ocr_space_client import OcrSpaceError
from app.services.scryfall_client import ScryfallCard, ScryfallError

_SAMPLE_CARD = ScryfallCard(
    scryfall_id="abc-123",
    name="Lightning Bolt",
    set_name="Masters 25",
    set_code="a25",
    collector_number="133",
    rarity="common",
    mana_cost="{R}",
    type_line="Instant",
    oracle_text="Lightning Bolt deals 3 damage to any target.",
    image_url="https://example.com/card.jpg",
    prices={"usd": "0.25"},
)


_M11_REPRINT = ScryfallCard(
    scryfall_id="def-456",
    name="Lightning Bolt",
    set_name="Magic 2011",
    set_code="m11",
    collector_number="146",
    rarity="common",
    mana_cost="{R}",
    type_line="Instant",
    oracle_text="Lightning Bolt deals 3 damage to any target.",
    image_url="https://example.com/m11-card.jpg",
    prices={"usd": "0.15"},
)


def _patch_vision(raw_text=None, error=None):
    if error is not None:
        return patch("app.services.enrichment_service.detect_text", side_effect=error)
    return patch("app.services.enrichment_service.detect_text", return_value=raw_text)


def _patch_scryfall(card=None, error=None):
    if error is not None:
        return patch("app.services.enrichment_service.search_by_name", side_effect=error)
    return patch("app.services.enrichment_service.search_by_name", return_value=card)


class TestEnrichImage:
    def test_no_text_detected_is_unrecognized_with_no_ocr_text_reason(self):
        with _patch_vision(raw_text=None):
            result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "no_ocr_text"
        assert result.ocr.raw_text is None
        assert result.timing.total_ms >= 0

    def test_text_with_no_parseable_name_is_unrecognized_with_no_ocr_text_reason(self):
        with _patch_vision(raw_text="   \n   "):
            result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "no_ocr_text"

    def test_vision_config_missing_maps_to_config_missing_error(self, monkeypatch):
        monkeypatch.setattr("app.services.enrichment_service.settings.ocr_space_api_key", None)
        with _patch_vision(error=OcrSpaceError("OCR_SPACE_API_KEY is not configured")):
            result = enrich_image(b"fake-image")

        assert isinstance(result, ErrorEnrichment)
        assert result.code == "CONFIG_MISSING"

    def test_vision_provider_failure_maps_to_ocr_provider_error(self, monkeypatch):
        monkeypatch.setattr("app.services.enrichment_service.settings.ocr_space_api_key", "key")
        with _patch_vision(error=OcrSpaceError("OCR.space returned status 403")):
            result = enrich_image(b"fake-image")

        assert isinstance(result, ErrorEnrichment)
        assert result.code == "OCR_PROVIDER_ERROR"

    def test_scryfall_unavailable_downgrades_to_unrecognized_not_a_5xx(self):
        with _patch_vision(raw_text="Lightning Bolt\n133/264"):
            with _patch_scryfall(error=ScryfallError("Scryfall request failed")):
                result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "scryfall_unavailable"

    def test_no_scryfall_match_is_unrecognized(self):
        with _patch_vision(raw_text="Not A Real Card\n133/264"):
            with _patch_scryfall(card=None):
                result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "no_scryfall_match"

    def test_falls_through_to_the_next_candidate_when_the_first_has_no_match(self):
        # "Screen Chrome" stands in for a noise line that outranks the real
        # name in OCR order but doesn't correspond to any real card.
        with _patch_vision(raw_text="Screen Chrome\nLightning Bolt"):
            with patch(
                "app.services.enrichment_service.search_by_name",
                side_effect=[None, _SAMPLE_CARD],
            ) as mock_search:
                result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)
        assert result.match.name == "Lightning Bolt"
        # Reports the candidate that actually matched, not the topmost OCR guess.
        assert result.ocr.parsed_name == "Lightning Bolt"
        assert mock_search.call_count == 2

    def test_stops_trying_candidates_once_scryfall_is_unavailable(self):
        with _patch_vision(raw_text="Screen Chrome\nLightning Bolt"):
            with patch(
                "app.services.enrichment_service.search_by_name",
                side_effect=ScryfallError("Scryfall request failed"),
            ) as mock_search:
                result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "scryfall_unavailable"
        assert mock_search.call_count == 1

    def test_collector_number_mismatch_downgrades_to_unrecognized(self):
        # 200/264 is a plausible (numerator <= denominator) but wrong number
        # for _SAMPLE_CARD, whose real collector number is 133, and no
        # printing exists with that exact number either.
        with _patch_vision(raw_text="Lightning Bolt\n200/264"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                with patch(
                    "app.services.enrichment_service.search_by_name_and_number", return_value=None
                ) as mock_reprint:
                    result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "number_mismatch"
        mock_reprint.assert_called_once_with("Lightning Bolt", "200")

    def test_number_mismatch_resolves_via_the_matching_reprint(self):
        # Scryfall's default (fuzzy, no set) lookup returns the a25 printing,
        # but the OCR'd number (146) points at a genuine different printing
        # of the same card — the m11 reprint — which should be used instead
        # of discarding an otherwise-confident name match.
        with _patch_vision(raw_text="Lightning Bolt\n146/249"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                with patch(
                    "app.services.enrichment_service.search_by_name_and_number",
                    return_value=_M11_REPRINT,
                ) as mock_reprint:
                    result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)
        assert result.match.set_code == "m11"
        assert result.match.collector_number == "146"
        mock_reprint.assert_called_once_with("Lightning Bolt", "146")

    def test_matching_collector_numbers_produce_a_match(self):
        with _patch_vision(raw_text="Lightning Bolt\n133/264"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)
        assert result.match.name == "Lightning Bolt"
        assert result.match.scryfall_id == "abc-123"

    def test_leading_zeros_do_not_cause_a_false_mismatch(self):
        with _patch_vision(raw_text="Lightning Bolt\n0133/264"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)

    def test_match_without_an_ocr_number_is_still_confident(self):
        with _patch_vision(raw_text="Lightning Bolt"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)

    def test_an_unexpected_exception_never_propagates(self):
        with patch(
            "app.services.enrichment_service.parse_ocr_text", side_effect=RuntimeError("boom")
        ):
            with _patch_vision(raw_text="Lightning Bolt"):
                result = enrich_image(b"fake-image")

        assert isinstance(result, ErrorEnrichment)
        assert result.code == "INTERNAL_ERROR"

    def test_timing_fields_are_populated_across_the_pipeline(self):
        with _patch_vision(raw_text="Lightning Bolt\n133/264"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                result = enrich_image(b"fake-image")

        assert isinstance(result, MatchedEnrichment)
        assert result.timing.ocr_ms >= 0
        assert result.timing.match_ms >= 0
        assert result.timing.total_ms >= result.timing.ocr_ms
