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

    def test_collector_number_mismatch_downgrades_to_unrecognized(self):
        with _patch_vision(raw_text="Lightning Bolt\n999/264"):
            with _patch_scryfall(card=_SAMPLE_CARD):
                result = enrich_image(b"fake-image")

        assert isinstance(result, UnrecognizedEnrichment)
        assert result.reason == "number_mismatch"

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
