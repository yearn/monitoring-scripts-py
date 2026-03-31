"""Tests for utils/paste.py."""

import unittest
from unittest.mock import MagicMock, patch

from utils.paste import upload_to_paste


class TestUploadToPaste(unittest.TestCase):
    """Tests for upload_to_paste."""

    def test_empty_content_returns_empty(self) -> None:
        result = upload_to_paste("")
        self.assertEqual(result, "")

    @patch("utils.paste.requests.post")
    def test_successful_upload(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = '"https://dpaste.com/abc123"\n'
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = upload_to_paste("Some content", title="Test")
        self.assertEqual(result, "https://dpaste.com/abc123")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs[1]["data"]["content"], "Some content")
        self.assertEqual(call_kwargs[1]["data"]["title"], "Test")
        self.assertEqual(call_kwargs[1]["data"]["expiry_days"], 7)

    @patch("utils.paste.requests.post")
    def test_custom_expiry(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = "https://dpaste.com/xyz789"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = upload_to_paste("Content", expiry_days=15)
        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs[1]["data"]["expiry_days"], 15)
        self.assertEqual(result, "https://dpaste.com/xyz789")

    @patch("utils.paste.requests.post")
    def test_request_failure_returns_empty(self, mock_post: MagicMock) -> None:
        import requests

        mock_post.side_effect = requests.RequestException("Connection error")
        result = upload_to_paste("Some content")
        self.assertEqual(result, "")

    @patch("utils.paste.requests.post")
    def test_no_title(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = "https://dpaste.com/notitle"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        upload_to_paste("Content only")
        call_kwargs = mock_post.call_args
        self.assertNotIn("title", call_kwargs[1]["data"])


if __name__ == "__main__":
    unittest.main()
