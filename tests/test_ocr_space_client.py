from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.ocr_space_client import OcrSpaceError, detect_text


def _mock_response(status_code: int, json_body: dict, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.text = text
    return response


class TestDetectText:
    def test_raises_when_api_key_is_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", None)

        with pytest.raises(OcrSpaceError, match="not configured"):
            detect_text(b"fake-image-bytes")

    def test_returns_parsed_text_on_success(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")
        body = {
            "IsErroredOnProcessing": False,
            "ParsedResults": [{"ParsedText": "Lightning Bolt\r\n133/264\r\n"}],
        }

        with patch("app.services.ocr_space_client.httpx.post", return_value=_mock_response(200, body)):
            result = detect_text(b"fake-image-bytes")

        assert result == "Lightning Bolt\r\n133/264\r\n"

    def test_returns_none_when_parsed_text_is_empty(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")
        body = {"IsErroredOnProcessing": False, "ParsedResults": [{"ParsedText": "   "}]}

        with patch("app.services.ocr_space_client.httpx.post", return_value=_mock_response(200, body)):
            result = detect_text(b"fake-image-bytes")

        assert result is None

    def test_returns_none_when_there_are_no_parsed_results(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")
        body = {"IsErroredOnProcessing": False, "ParsedResults": []}

        with patch("app.services.ocr_space_client.httpx.post", return_value=_mock_response(200, body)):
            result = detect_text(b"fake-image-bytes")

        assert result is None

    def test_raises_when_the_api_reports_a_processing_error(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")
        body = {"IsErroredOnProcessing": True, "ErrorMessage": "Unsupported file format"}

        with patch("app.services.ocr_space_client.httpx.post", return_value=_mock_response(200, body)):
            with pytest.raises(OcrSpaceError, match="Unsupported file format"):
                detect_text(b"fake-image-bytes")

    def test_raises_on_non_200_status(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")

        with patch(
            "app.services.ocr_space_client.httpx.post",
            return_value=_mock_response(403, {}, text="forbidden"),
        ):
            with pytest.raises(OcrSpaceError, match="status 403"):
                detect_text(b"fake-image-bytes")

    def test_wraps_a_network_failure(self, monkeypatch):
        monkeypatch.setattr("app.services.ocr_space_client.settings.ocr_space_api_key", "test-key")

        with patch(
            "app.services.ocr_space_client.httpx.post",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(OcrSpaceError, match="request failed"):
                detect_text(b"fake-image-bytes")
