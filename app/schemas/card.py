from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CardStatus = Literal["pending", "enriched", "unrecognized", "error"]


class CardCreate(BaseModel):
    status: CardStatus
    thumbnail_base64: str | None = None
    raw_ocr_text: str | None = None
    ocr_parsed_name: str | None = None
    ocr_parsed_number: str | None = None
    matched_name: str | None = None
    matched_set_name: str | None = None
    matched_set_code: str | None = None
    matched_collector_number: str | None = None
    matched_scryfall_id: str | None = None
    matched_image_url: str | None = None
    matched_data: dict | None = None
    enrichment_error: str | None = None


class CardRead(CardCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
