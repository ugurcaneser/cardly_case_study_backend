from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.schemas.enrichment import (
    ErrorEnrichmentSchema,
    MatchResultSchema,
    MatchedEnrichmentSchema,
    OcrResultSchema,
    TimingSchema,
    UnrecognizedEnrichmentSchema,
)
from app.services.enrichment_service import (
    MatchedEnrichment,
    UnrecognizedEnrichment,
    enrich_image,
)

router = APIRouter(prefix="/enrich", tags=["enrich"])

MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

_ERROR_STATUS_CODES = {
    "INVALID_IMAGE": 400,
    "CONFIG_MISSING": 503,
    "OCR_PROVIDER_ERROR": 502,
    "INTERNAL_ERROR": 500,
}


@router.post("")
def enrich(image: UploadFile = File(...)) -> JSONResponse:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        return _error_response("INVALID_IMAGE", f"Unsupported content type: {image.content_type}")

    image_bytes = image.file.read()

    if not image_bytes:
        return _error_response("INVALID_IMAGE", "Uploaded image is empty")
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        return _error_response("INVALID_IMAGE", "Uploaded image exceeds the 8MB limit")

    result = enrich_image(image_bytes)

    if isinstance(result, MatchedEnrichment):
        schema = MatchedEnrichmentSchema(
            status="matched",
            ocr=OcrResultSchema.model_validate(result.ocr, from_attributes=True),
            match=MatchResultSchema.model_validate(result.match, from_attributes=True),
            timing=TimingSchema.model_validate(result.timing, from_attributes=True),
        )
        return JSONResponse(status_code=200, content=schema.model_dump(by_alias=True))

    if isinstance(result, UnrecognizedEnrichment):
        schema = UnrecognizedEnrichmentSchema(
            status="unrecognized",
            ocr=OcrResultSchema.model_validate(result.ocr, from_attributes=True),
            reason=result.reason,
            timing=TimingSchema.model_validate(result.timing, from_attributes=True),
        )
        return JSONResponse(status_code=200, content=schema.model_dump(by_alias=True))

    return _error_response(result.code, result.message)


def _error_response(code: str, message: str) -> JSONResponse:
    schema = ErrorEnrichmentSchema(status="error", code=code, message=message)
    return JSONResponse(
        status_code=_ERROR_STATUS_CODES[code], content=schema.model_dump(by_alias=True)
    )
