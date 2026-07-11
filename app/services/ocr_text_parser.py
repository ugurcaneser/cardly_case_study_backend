import re
from dataclasses import dataclass, field

_COLLECTOR_NUMBER_PATTERN = re.compile(r"\b(\d{1,4})\s*/\s*(\d{1,4})\b")
_MIN_NAME_ALPHA_CHARS = 3
_MAX_NAME_CANDIDATES = 6


@dataclass(frozen=True)
class ParsedOcrText:
    parsed_name: str | None
    parsed_number: str | None
    # Ranked guesses for the card name, topmost-first — see _parse_name_candidates.
    name_candidates: tuple[str, ...] = field(default_factory=tuple)


def parse_ocr_text(raw_text: str | None) -> ParsedOcrText:
    """Derives a likely card name and collector number from raw OCR text.

    Pure and defensive by design: OCR output from a real card photo is noisy
    (rules text, flavor text, copyright lines), so this never raises — it
    degrades to `None`/empty fields instead, letting the caller treat the
    card as unrecognized rather than crash the enrichment request.
    """
    if not raw_text or not raw_text.strip():
        return ParsedOcrText(parsed_name=None, parsed_number=None)

    candidates = _parse_name_candidates(raw_text)

    return ParsedOcrText(
        parsed_name=candidates[0] if candidates else None,
        parsed_number=_parse_collector_number(raw_text),
        name_candidates=candidates,
    )


def _parse_name_candidates(raw_text: str) -> tuple[str, ...]:
    """Ranks lines by how likely they are to be the printed card name.

    A clean photo of a physical card has the name on (or near) the first
    line, but noisy input can push real junk above it — glare, a copyright
    line OCR'd first, or (seen in practice) someone photographing a
    screenshot of the card with browser/window chrome above it, which reads
    as short tokens like "ms" before ever reaching the real name. Rather
    than commit to a single guess, this returns several ranked candidates
    (topmost-first, deduped, capped) so the caller can try each against
    Scryfall in order and stop at the first genuine match.
    """
    seen: set[str] = set()
    candidates: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not _looks_like_a_name(candidate):
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        if len(candidates) >= _MAX_NAME_CANDIDATES:
            break
    return tuple(candidates)


def _looks_like_a_name(candidate: str) -> bool:
    if "..." in candidate:
        return False  # truncated filename/UI label artifact, e.g. "mh3-59-dreamt..."
    return sum(char.isalpha() for char in candidate) >= _MIN_NAME_ALPHA_CHARS


def _parse_collector_number(raw_text: str) -> str | None:
    # A creature's printed power/toughness (e.g. "7/5") matches the same
    # digit-slash-digit shape as a real collector number ("059/291") and is
    # often the only such pattern OCR picks up when the actual collector
    # line is cut off or unreadable. A genuine collector number is always
    # <= the set's total card count, so requiring numerator <= denominator
    # filters out P/T false positives like "7/5" without needing to touch
    # cards whose toughness happens to exceed their power.
    for match in _COLLECTOR_NUMBER_PATTERN.finditer(raw_text):
        numerator, denominator = int(match.group(1)), int(match.group(2))
        if numerator <= denominator:
            return f"{match.group(1)}/{match.group(2)}"
    return None
