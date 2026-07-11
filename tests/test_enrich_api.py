import io

from app.api.routes import enrich as enrich_route
from app.services.enrichment_service import (
    ErrorEnrichment,
    MatchedEnrichment,
    MatchResult,
    OcrResult,
    Timing,
    UnrecognizedEnrichment,
)

FAKE_IMAGE = ("card.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")


def test_enrich_matched(client, monkeypatch):
    result = MatchedEnrichment(
        ocr=OcrResult(raw_text="Lightning Bolt\n133264", parsed_name="Lightning Bolt", parsed_number="133/264"),
        match=MatchResult(
            scryfall_id="abc-123",
            name="Lightning Bolt",
            set_name="Magic 2010",
            set_code="m10",
            collector_number="133",
            rarity="common",
            mana_cost="{R}",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            image_url="https://example.com/bolt.jpg",
            prices={"usd": "0.25"},
        ),
        timing=Timing(ocr_ms=100.0, match_ms=50.0, total_ms=150.0),
    )
    monkeypatch.setattr(enrich_route, "enrich_image", lambda image_bytes: result)

    response = client.post("/enrich", files={"image": FAKE_IMAGE})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"
    assert data["ocr"]["rawText"] == "Lightning Bolt\n133264"
    assert data["ocr"]["parsedName"] == "Lightning Bolt"
    assert data["match"]["scryfallId"] == "abc-123"
    assert data["match"]["setName"] == "Magic 2010"
    assert data["timing"]["totalMs"] == 150.0


def test_enrich_unrecognized(client, monkeypatch):
    result = UnrecognizedEnrichment(
        ocr=OcrResult(raw_text=None, parsed_name=None, parsed_number=None),
        reason="no_ocr_text",
        timing=Timing(ocr_ms=80.0, match_ms=0.0, total_ms=80.0),
    )
    monkeypatch.setattr(enrich_route, "enrich_image", lambda image_bytes: result)

    response = client.post("/enrich", files={"image": FAKE_IMAGE})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unrecognized"
    assert data["reason"] == "no_ocr_text"
    assert data["match"] is None


def test_enrich_ocr_provider_error(client, monkeypatch):
    result = ErrorEnrichment(code="OCR_PROVIDER_ERROR", message="OCR.space timed out")
    monkeypatch.setattr(enrich_route, "enrich_image", lambda image_bytes: result)

    response = client.post("/enrich", files={"image": FAKE_IMAGE})

    assert response.status_code == 502
    data = response.json()
    assert data["status"] == "error"
    assert data["code"] == "OCR_PROVIDER_ERROR"
    assert data["message"] == "OCR.space timed out"


def test_enrich_config_missing_error(client, monkeypatch):
    result = ErrorEnrichment(code="CONFIG_MISSING", message="OCR_SPACE_API_KEY is not set")
    monkeypatch.setattr(enrich_route, "enrich_image", lambda image_bytes: result)

    response = client.post("/enrich", files={"image": FAKE_IMAGE})

    assert response.status_code == 503
    assert response.json()["code"] == "CONFIG_MISSING"


def test_enrich_internal_error(client, monkeypatch):
    result = ErrorEnrichment(code="INTERNAL_ERROR", message="boom")
    monkeypatch.setattr(enrich_route, "enrich_image", lambda image_bytes: result)

    response = client.post("/enrich", files={"image": FAKE_IMAGE})

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"


def test_enrich_rejects_unsupported_content_type(client):
    response = client.post("/enrich", files={"image": ("card.txt", io.BytesIO(b"not an image"), "text/plain")})

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IMAGE"


def test_enrich_rejects_empty_file(client):
    response = client.post("/enrich", files={"image": ("card.jpg", io.BytesIO(b""), "image/jpeg")})

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IMAGE"


def test_enrich_rejects_oversized_file(client):
    oversized = io.BytesIO(b"0" * (enrich_route.MAX_IMAGE_SIZE_BYTES + 1))
    response = client.post("/enrich", files={"image": ("card.jpg", oversized, "image/jpeg")})

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IMAGE"
