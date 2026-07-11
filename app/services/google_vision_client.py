import base64

import httpx

from app.core.config import settings

VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"
_REQUEST_TIMEOUT_SECONDS = 15.0


class GoogleVisionError(Exception):
    """Raised for a genuine Vision API failure (missing config, auth/quota, network, malformed response).

    Not raised when the API simply finds no text in the image — that's a
    legitimate result (`detect_text` returns `None`), not an error.
    """


def detect_text(image_bytes: bytes) -> str | None:
    """Runs TEXT_DETECTION on the given image and returns the full detected text block, or `None` if no text was found."""
    if not settings.google_vision_api_key:
        raise GoogleVisionError("GOOGLE_VISION_API_KEY is not configured")

    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "TEXT_DETECTION"}],
            }
        ]
    }

    try:
        response = httpx.post(
            VISION_API_URL,
            params={"key": settings.google_vision_api_key},
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise GoogleVisionError(f"Vision API request failed: {exc}") from exc

    if response.status_code != 200:
        raise GoogleVisionError(f"Vision API returned status {response.status_code}: {response.text}")

    result = response.json().get("responses", [{}])[0]

    if "error" in result:
        raise GoogleVisionError(f"Vision API error: {result['error']}")

    annotations = result.get("textAnnotations")
    if not annotations:
        return None

    return annotations[0].get("description")
