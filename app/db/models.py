from datetime import datetime

from sqlalchemy import Column, CheckConstraint, ForeignKey, Integer, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class Card(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','enriched','unrecognized','error')",
            name="ck_card_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    # Nullable so pre-multi-tenancy rows don't need a backfill — they simply
    # stop matching any device's filtered queries instead of being deleted.
    user_id: str | None = Field(default=None, index=True)
    status: str
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
    matched_data: dict | None = Field(default=None, sa_column=Column(JSON))
    enrichment_error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Collection(SQLModel, table=True):
    # Name uniqueness is per-device, not global — two devices may each have
    # their own "Vintage" collection.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_collection_user_id_name"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str | None = Field(default=None, index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CollectionCard(SQLModel, table=True):
    collection_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("collection.id", ondelete="CASCADE"), primary_key=True
        )
    )
    card_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("card.id", ondelete="CASCADE"), primary_key=True, index=True
        )
    )
    added_at: datetime = Field(default_factory=datetime.utcnow)
