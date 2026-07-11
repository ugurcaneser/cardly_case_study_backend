from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for the /enrich response schemas only — cards/collections stay snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class OcrResultSchema(CamelModel):
    raw_text: str | None
    parsed_name: str | None
    parsed_number: str | None


class TimingSchema(CamelModel):
    ocr_ms: float
    match_ms: float
    total_ms: float


class MatchResultSchema(CamelModel):
    source: Literal["scryfall"]
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


class MatchedEnrichmentSchema(CamelModel):
    status: Literal["matched"]
    ocr: OcrResultSchema
    match: MatchResultSchema
    timing: TimingSchema


class UnrecognizedEnrichmentSchema(CamelModel):
    status: Literal["unrecognized"]
    ocr: OcrResultSchema
    reason: Literal["no_ocr_text", "no_scryfall_match", "scryfall_unavailable", "number_mismatch"]
    timing: TimingSchema
    match: None = None


class ErrorEnrichmentSchema(CamelModel):
    status: Literal["error"]
    code: Literal["INVALID_IMAGE", "OCR_PROVIDER_ERROR", "CONFIG_MISSING", "INTERNAL_ERROR"]
    message: str
