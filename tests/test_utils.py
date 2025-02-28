"""Tests for utility functions."""

import os
import unittest
from unittest.mock import patch

from utils.config import Config, ProtocolConfig
from utils.telegram import TelegramError, send_telegram_message


class TestConfig(unittest.TestCase):
    """Tests for the Config class."""

    def test_get_env(self):
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            self.assertEqual(Config.get_env("TEST_VAR"), "test_value")
            self.assertEqual(Config.get_env("NONEXISTENT_VAR", "default"), "default")

    def test_get_env_int(self):
        with patch.dict(os.environ, {"TEST_INT": "42", "TEST_INVALID": "not_an_int"}):
            self.assertEqual(Config.get_env_int("TEST_INT", 0), 42)
            self.assertEqual(Config.get_env_int("NONEXISTENT_VAR", 10), 10)
            self.assertEqual(Config.get_env_int("TEST_INVALID", 10), 10)

    def test_get_env_float(self):
        with patch.dict(os.environ, {"TEST_FLOAT": "3.14", "TEST_INVALID": "not_a_float"}):
            self.assertAlmostEqual(Config.get_env_float("TEST_FLOAT", 0.0), 3.14)
            self.assertAlmostEqual(Config.get_env_float("NONEXISTENT_VAR", 2.71), 2.71)
            self.assertAlmostEqual(Config.get_env_float("TEST_INVALID", 2.71), 2.71)

    def test_get_env_bool(self):
        with patch.dict(
            os.environ,
            {
                "TEST_TRUE1": "true",
                "TEST_TRUE2": "yes",
                "TEST_TRUE3": "1",
                "TEST_FALSE": "false",
            },
        ):
            self.assertTrue(Config.get_env_bool("TEST_TRUE1", False))
            self.assertTrue(Config.get_env_bool("TEST_TRUE2", False))
            self.assertTrue(Config.get_env_bool("TEST_TRUE3", False))
            self.assertFalse(Config.get_env_bool("TEST_FALSE", True))
            self.assertTrue(Config.get_env_bool("NONEXISTENT_VAR", True))

    def test_get_protocol_config(self):
        with patch.dict(
            os.environ,
            {
                "AAVE_ALERT_THRESHOLD": "0.96",
                "AAVE_CRITICAL_THRESHOLD": "0.99",
                "AAVE_ENABLE_NOTIFICATIONS": "false",
            },
        ):
            config = Config.get_protocol_config("aave")
            self.assertIsInstance(config, ProtocolConfig)
            self.assertEqual(config.name, "aave")
            self.assertAlmostEqual(config.alert_threshold, 0.96)
            self.assertAlmostEqual(config.critical_threshold, 0.99)
            self.assertFalse(config.enable_notifications)


class TestTelegram(unittest.TestCase):
    """Tests for Telegram utility functions."""

    @patch("utils.telegram.requests.get")
    def test_send_telegram_message_success(self, mock_get):
        # Setup mock response
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Test with environment variables
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN_TEST": "test_token",
                "TELEGRAM_CHAT_ID_TEST": "test_chat_id",
            },
        ):
            # Should not raise any exceptions
            send_telegram_message("Test message", "test")

            # Verify the request was made with the correct parameters
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            self.assertEqual(kwargs["params"]["text"], "Test message")
            self.assertEqual(kwargs["params"]["parse_mode"], "Markdown")

    @patch("utils.telegram.requests.get")
    def test_send_telegram_message_missing_credentials(self, mock_get):
        # Test with missing environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise exceptions but print a warning
            with patch("builtins.print") as mock_print:
                send_telegram_message("Test message", "test")
                mock_print.assert_any_call("Warning: Missing Telegram credentials for test")

            # Verify no request was made
            mock_get.assert_not_called()

    @patch("utils.telegram.requests.get")
    def test_send_telegram_message_failure(self, mock_get):
        # Setup mock response for failure
        mock_get.side_effect = Exception("Connection error")

        # Test with environment variables
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN_TEST": "test_token",
                "TELEGRAM_CHAT_ID_TEST": "test_chat_id",
            },
        ):
            # Should raise TelegramError
            with self.assertRaises(TelegramError):
                send_telegram_message("Test message", "test")


if __name__ == "__main__":
    unittest.main()
