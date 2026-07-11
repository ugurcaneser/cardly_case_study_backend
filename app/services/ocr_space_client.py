import httpx

from app.core.config import settings

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"
_REQUEST_TIMEOUT_SECONDS = 20.0


class OcrSpaceError(Exception):
    """Raised for a genuine OCR.space failure (missing config, auth/quota, network, malformed
    response, or a reported processing error).

    Not raised when OCR.space simply finds no text in the image — that's a
    legitimate result (`detect_text` returns `None`), not an error.
    """


def detect_text(image_bytes: bytes) -> str | None:
    if not settings.ocr_space_api_key:
        raise OcrSpaceError("OCR_SPACE_API_KEY is not configured")

    try:
        response = httpx.post(
            OCR_SPACE_API_URL,
            data={
                "apikey": settings.ocr_space_api_key,
                "OCREngine": "2",
                "scale": "true",
                "detectOrientation": "true",
            },
            files={"file": ("card.jpg", image_bytes, "image/jpeg")},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise OcrSpaceError(f"OCR.space request failed: {exc}") from exc

    if response.status_code != 200:
        raise OcrSpaceError(f"OCR.space returned status {response.status_code}: {response.text}")

    data = response.json()

    if data.get("IsErroredOnProcessing"):
        raise OcrSpaceError(f"OCR.space processing error: {data.get('ErrorMessage')}")

    parsed_results = data.get("ParsedResults") or []
    if not parsed_results:
        return None

    text = parsed_results[0].get("ParsedText")
    if not text or not text.strip():
        return None

    return text
