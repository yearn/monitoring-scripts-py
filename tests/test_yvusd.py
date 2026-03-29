import unittest
from unittest.mock import MagicMock, patch

from utils.chains import Chain
from yearn.yvusd import (
    CCTP_REPORT_SKEW_HOURS,
    CCTP_REPORT_STALENESS_HOURS,
    check_large_cooldowns,
    check_strategy_staleness,
)


class TestYvUsdCctpChecks(unittest.TestCase):
    @patch("yearn.yvusd.send_alert")
    @patch("yearn.yvusd.ChainManager.get_client")
    def test_alerts_on_report_skew_between_local_and_remote(self, mock_get_client: MagicMock, mock_send_alert: MagicMock):
        now = 1_000_000
        local_last_report = now - 3600
        remote_last_report = now - int((CCTP_REPORT_SKEW_HOURS + 2) * 3600)

        remote_vault = MagicMock()
        remote_vault.functions.strategies.return_value.call.return_value = (
            1,
            remote_last_report,
            100_000_000,
            0,
        )
        remote_client = MagicMock()
        remote_client.eth.contract.return_value = remote_vault
        mock_get_client.return_value = remote_client

        mainnet_vault = MagicMock()
        client = MagicMock()
        client.eth.contract.return_value = mainnet_vault
        client.batch_requests.return_value.__enter__.return_value = MagicMock()
        client.batch_requests.return_value.__exit__.return_value = False
        client.execute_batch.return_value = [(1, local_last_report, 100_000_000, 0)]

        api_data = {
            "0x696d02Db93291651ED510704c9b286841d506987": {
                "meta": {
                    "strategies": [
                        {
                            "address": "0x1983923e5a3591AFe036d38A8C8011e66Cd76e9E",
                            "meta": {
                                "name": "Arbitrum Yearn Degen Morpho Compounder",
                                "type": "cross-chain",
                                "remote_chain_id": Chain.ARBITRUM.chain_id,
                                "remote_vault": "0x78b7774c4368df8f2c115Abf6210F557753a6aC5",
                                "remote_counterpart": "0xaDa882B1BcB9B658b354ade0cE64586A88cb6849",
                            },
                        }
                    ]
                }
            }
        }

        with patch("yearn.yvusd.time.time", return_value=now):
            check_strategy_staleness(client, api_data)

        mock_send_alert.assert_called_once()
        message = mock_send_alert.call_args.args[0].message
        self.assertIn("report skew", message)
        self.assertIn("Arbitrum Yearn Degen Morpho Compounder", message)

    @patch("yearn.yvusd.send_alert")
    @patch("yearn.yvusd.ChainManager.get_client")
    def test_alerts_on_remote_staleness(self, mock_get_client: MagicMock, mock_send_alert: MagicMock):
        now = 1_000_000
        stale_seconds = int((CCTP_REPORT_STALENESS_HOURS + 1) * 3600)

        remote_vault = MagicMock()
        remote_vault.functions.strategies.return_value.call.return_value = (
            1,
            now - stale_seconds,
            200_000_000,
            0,
        )
        remote_client = MagicMock()
        remote_client.eth.contract.return_value = remote_vault
        mock_get_client.return_value = remote_client

        client = MagicMock()
        client.eth.contract.return_value = MagicMock()
        client.batch_requests.return_value.__enter__.return_value = MagicMock()
        client.batch_requests.return_value.__exit__.return_value = False
        client.execute_batch.return_value = [(1, now - 3600, 100_000_000, 0)]

        api_data = {
            "0x696d02Db93291651ED510704c9b286841d506987": {
                "meta": {
                    "strategies": [
                        {
                            "address": "0x2F56D106C6Df739bdbb777C2feE79FFaED88D179",
                            "meta": {
                                "name": "Arbitrum syrupUSDC/USDC Morpho Looper",
                                "type": "cross-chain",
                                "remote_chain_id": Chain.ARBITRUM.chain_id,
                                "remote_vault": "0xBCf08997C34183d1b7B0f99e13aCeACFBA88E453",
                                "remote_counterpart": "0xAA442539f43d9A864e26e56E5C8Ee791E9Df7dA2",
                            },
                        }
                    ]
                }
            }
        }

        with patch("yearn.yvusd.time.time", return_value=now):
            check_strategy_staleness(client, api_data)

        mock_send_alert.assert_called_once()
        self.assertIn("report stale", mock_send_alert.call_args.args[0].message)


class TestYvUsdCooldownScanning(unittest.TestCase):
    @patch("yearn.yvusd.set_cache_value")
    @patch("yearn.yvusd.get_cache_value", return_value=123)
    def test_does_not_advance_cache_when_log_fetch_fails(self, mock_get_cache: MagicMock, mock_set_cache: MagicMock):
        client = MagicMock()
        client.eth.block_number = 200

        locked = MagicMock()
        locked.events.CooldownStarted.get_logs.side_effect = RuntimeError("rpc failure")
        client.eth.contract.return_value = locked

        check_large_cooldowns(client)

        mock_set_cache.assert_not_called()


if __name__ == "__main__":
    unittest.main()
