import re
from dataclasses import dataclass

_COLLECTOR_NUMBER_PATTERN = re.compile(r"\b(\d{1,4})\s*/\s*(\d{1,4})\b")


@dataclass(frozen=True)
class ParsedOcrText:
    parsed_name: str | None
    parsed_number: str | None


def parse_ocr_text(raw_text: str | None) -> ParsedOcrText:
    """Derives a likely card name and collector number from raw OCR text.

    Pure and defensive by design: OCR output from a real card photo is noisy
    (rules text, flavor text, copyright lines), so this never raises — it
    degrades to `None` fields instead, letting the caller treat the card as
    unrecognized rather than crash the enrichment request.
    """
    if not raw_text or not raw_text.strip():
        return ParsedOcrText(parsed_name=None, parsed_number=None)

    return ParsedOcrText(
        parsed_name=_parse_name(raw_text),
        parsed_number=_parse_collector_number(raw_text),
    )


def _parse_name(raw_text: str) -> str | None:
    # The card name is conventionally the topmost printed text; skip any
    # leading line that has no letters (e.g. a stray collector number or
    # set-symbol artifact OCR'd before the name).
    for line in raw_text.splitlines():
        candidate = line.strip()
        if candidate and any(char.isalpha() for char in candidate):
            return candidate
    return None


def _parse_collector_number(raw_text: str) -> str | None:
    match = _COLLECTOR_NUMBER_PATTERN.search(raw_text)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"
