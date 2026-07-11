from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.google_vision_client import GoogleVisionError, detect_text


def _mock_response(status_code: int, json_body: dict) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.text = str(json_body)
    return response


class TestDetectText:
    def test_raises_when_api_key_is_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", None)

        with pytest.raises(GoogleVisionError, match="not configured"):
            detect_text(b"fake-image-bytes")

    def test_returns_full_text_block_on_success(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", "test-key")
        body = {"responses": [{"textAnnotations": [{"description": "Lightning Bolt\n133/264"}]}]}

        with patch("app.services.google_vision_client.httpx.post", return_value=_mock_response(200, body)):
            result = detect_text(b"fake-image-bytes")

        assert result == "Lightning Bolt\n133/264"

    def test_returns_none_when_no_text_is_found(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", "test-key")
        body = {"responses": [{}]}

        with patch("app.services.google_vision_client.httpx.post", return_value=_mock_response(200, body)):
            result = detect_text(b"fake-image-bytes")

        assert result is None

    def test_raises_on_non_200_status(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", "test-key")

        with patch(
            "app.services.google_vision_client.httpx.post",
            return_value=_mock_response(403, {"error": "forbidden"}),
        ):
            with pytest.raises(GoogleVisionError, match="status 403"):
                detect_text(b"fake-image-bytes")

    def test_raises_on_per_image_error_in_response_body(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", "test-key")
        body = {"responses": [{"error": {"code": 3, "message": "Bad image data"}}]}

        with patch("app.services.google_vision_client.httpx.post", return_value=_mock_response(200, body)):
            with pytest.raises(GoogleVisionError, match="Bad image data"):
                detect_text(b"fake-image-bytes")

    def test_wraps_a_network_failure(self, monkeypatch):
        monkeypatch.setattr("app.services.google_vision_client.settings.google_vision_api_key", "test-key")

        with patch(
            "app.services.google_vision_client.httpx.post",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(GoogleVisionError, match="request failed"):
                detect_text(b"fake-image-bytes")
