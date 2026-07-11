import logging
import time
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.services.ocr_space_client import OcrSpaceError, detect_text
from app.services.ocr_text_parser import parse_ocr_text
from app.services.scryfall_client import ScryfallError, search_by_name

logger = logging.getLogger("cardly.enrichment")

UnrecognizedReason = Literal[
    "no_ocr_text", "no_scryfall_match", "scryfall_unavailable", "number_mismatch"
]
ErrorCode = Literal["OCR_PROVIDER_ERROR", "CONFIG_MISSING", "INTERNAL_ERROR"]


@dataclass(frozen=True)
class OcrResult:
    raw_text: str | None
    parsed_name: str | None
    parsed_number: str | None


@dataclass(frozen=True)
class Timing:
    ocr_ms: float
    match_ms: float
    total_ms: float


@dataclass(frozen=True)
class MatchResult:
    scryfall_id: str
    name: str
    set_name: str
    set_code: str
    collector_number: str
    rarity: str
    mana_cost: str | None
    type_line: str
    oracle_text: str | None
    image_url: str | None
    prices: dict[str, str | None]
    source: Literal["scryfall"] = "scryfall"


@dataclass(frozen=True)
class MatchedEnrichment:
    ocr: OcrResult
    match: MatchResult
    timing: Timing
    status: Literal["matched"] = "matched"


@dataclass(frozen=True)
class UnrecognizedEnrichment:
    ocr: OcrResult
    reason: UnrecognizedReason
    timing: Timing
    status: Literal["unrecognized"] = "unrecognized"


@dataclass(frozen=True)
class ErrorEnrichment:
    code: ErrorCode
    message: str
    status: Literal["error"] = "error"


EnrichmentResult = MatchedEnrichment | UnrecognizedEnrichment | ErrorEnrichment


def enrich_image(image_bytes: bytes) -> EnrichmentResult:
    """Runs the full OCR -> parse -> Scryfall-match pipeline for a card photo.

    Never raises: every failure mode documented in the API contract (missing
    OCR text, no Scryfall match, Scryfall being down, a collector-number
    mismatch, or a genuinely unexpected exception) is caught here and turned
    into one of the three well-formed result shapes instead.
    """
    start = time.perf_counter()
    try:
        return _run_pipeline(image_bytes, start)
    except Exception as exc:  # noqa: BLE001 - last-resort guard, must never propagate
        logger.exception("Unhandled enrichment failure")
        return ErrorEnrichment(code="INTERNAL_ERROR", message=str(exc))


def _run_pipeline(image_bytes: bytes, start: float) -> EnrichmentResult:
    ocr_start = time.perf_counter()
    try:
        raw_text = detect_text(image_bytes)
    except OcrSpaceError as exc:
        logger.warning("OCR.space call failed: %s", exc)
        code: ErrorCode = "CONFIG_MISSING" if not settings.ocr_space_api_key else "OCR_PROVIDER_ERROR"
        return ErrorEnrichment(code=code, message=str(exc))
    ocr_ms = _elapsed_ms(ocr_start)

    parsed = parse_ocr_text(raw_text)
    ocr_result = OcrResult(
        raw_text=raw_text, parsed_name=parsed.parsed_name, parsed_number=parsed.parsed_number
    )

    if not parsed.parsed_name:
        return UnrecognizedEnrichment(
            ocr=ocr_result,
            reason="no_ocr_text",
            timing=Timing(ocr_ms=ocr_ms, match_ms=0.0, total_ms=_elapsed_ms(start)),
        )

    match_start = time.perf_counter()
    try:
        card = search_by_name(parsed.parsed_name)
    except ScryfallError as exc:
        logger.warning("Scryfall lookup failed: %s", exc)
        return UnrecognizedEnrichment(
            ocr=ocr_result,
            reason="scryfall_unavailable",
            timing=Timing(ocr_ms=ocr_ms, match_ms=_elapsed_ms(match_start), total_ms=_elapsed_ms(start)),
        )
    match_ms = _elapsed_ms(match_start)

    if card is None:
        return UnrecognizedEnrichment(
            ocr=ocr_result,
            reason="no_scryfall_match",
            timing=Timing(ocr_ms=ocr_ms, match_ms=match_ms, total_ms=_elapsed_ms(start)),
        )

    if _collector_numbers_conflict(parsed.parsed_number, card.collector_number):
        return UnrecognizedEnrichment(
            ocr=ocr_result,
            reason="number_mismatch",
            timing=Timing(ocr_ms=ocr_ms, match_ms=match_ms, total_ms=_elapsed_ms(start)),
        )

    return MatchedEnrichment(
        ocr=ocr_result,
        match=MatchResult(
            scryfall_id=card.scryfall_id,
            name=card.name,
            set_name=card.set_name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            rarity=card.rarity,
            mana_cost=card.mana_cost,
            type_line=card.type_line,
            oracle_text=card.oracle_text,
            image_url=card.image_url,
            prices=card.prices,
        ),
        timing=Timing(ocr_ms=ocr_ms, match_ms=match_ms, total_ms=_elapsed_ms(start)),
    )


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def _collector_numbers_conflict(ocr_number: str | None, scryfall_number: str) -> bool:
    """True only when both sides name a number and they disagree — a missing OCR number can't conflict."""
    if not ocr_number:
        return False
    ocr_numerator = ocr_number.split("/")[0].strip().lstrip("0") or "0"
    normalized_scryfall = scryfall_number.strip().lstrip("0") or "0"
    return ocr_numerator != normalized_scryfall
