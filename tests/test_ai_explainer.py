"""Tests for utils/ai_explainer.py."""

import unittest
from unittest.mock import MagicMock, patch

from timelock.calldata_decoder import DecodedCall
from utils.ai_explainer import (
    _build_prompt,
    _format_decoded_calls,
    _format_simulation_context,
    explain_transaction,
    format_explanation_line,
)
from utils.llm.base import LLMError
from utils.tenderly.simulation import AssetChange, SimulationResult, StateChange


class TestFormatDecodedCalls(unittest.TestCase):
    """Tests for _format_decoded_calls."""

    def test_single_call_no_params(self) -> None:
        calls = [DecodedCall(function_name="pause", signature="pause()")]
        result = _format_decoded_calls(calls)
        self.assertIn("Call 1: pause()", result)

    def test_single_call_with_params(self) -> None:
        calls = [
            DecodedCall(
                function_name="grantRole",
                signature="grantRole(bytes32,address)",
                params=[("bytes32", b"\x00" * 32), ("address", "0xABC")],
            )
        ]
        result = _format_decoded_calls(calls)
        self.assertIn("grantRole(bytes32,address)", result)
        self.assertIn("bytes32:", result)
        self.assertIn("address:", result)

    def test_multiple_calls(self) -> None:
        calls = [
            DecodedCall(function_name="pause", signature="pause()"),
            DecodedCall(function_name="unpause", signature="unpause()"),
        ]
        result = _format_decoded_calls(calls)
        self.assertIn("Call 1: pause()", result)
        self.assertIn("Call 2: unpause()", result)


class TestFormatSimulationContext(unittest.TestCase):
    """Tests for _format_simulation_context."""

    def test_successful_simulation(self) -> None:
        sim = SimulationResult(success=True, gas_used=50000)
        result = _format_simulation_context(sim)
        self.assertIn("SUCCESS", result)
        self.assertIn("50,000", result)

    def test_failed_simulation(self) -> None:
        sim = SimulationResult(success=False, gas_used=21000, error_message="execution reverted")
        result = _format_simulation_context(sim)
        self.assertIn("FAILED", result)
        self.assertIn("execution reverted", result)

    def test_with_asset_changes(self) -> None:
        sim = SimulationResult(
            success=True,
            gas_used=100000,
            asset_changes=[
                AssetChange(
                    token_address="0xToken",
                    token_name="USDC",
                    token_symbol="USDC",
                    from_address="0xA",
                    to_address="0xB",
                    amount="1000",
                    raw_amount="1000000000",
                    decimals=6,
                )
            ],
        )
        result = _format_simulation_context(sim)
        self.assertIn("Token transfers:", result)
        self.assertIn("USDC", result)

    def test_with_state_changes(self) -> None:
        sim = SimulationResult(
            success=True,
            gas_used=100000,
            state_changes=[
                StateChange(
                    contract_address="0xContract",
                    key="0x01",
                    original="0x00",
                    dirty="0x01",
                )
            ],
        )
        result = _format_simulation_context(sim)
        self.assertIn("State changes", result)
        self.assertIn("0xContract", result)

    def test_with_logs(self) -> None:
        sim = SimulationResult(
            success=True,
            gas_used=100000,
            logs=[{"name": "Transfer", "inputs": [{"soltype": {"name": "to"}, "value": "0xB"}]}],
        )
        result = _format_simulation_context(sim)
        self.assertIn("Events emitted", result)
        self.assertIn("Transfer", result)


class TestBuildPrompt(unittest.TestCase):
    """Tests for _build_prompt."""

    def test_basic_prompt(self) -> None:
        calls = [DecodedCall(function_name="pause", signature="pause()")]
        result = _build_prompt(target="0xTarget", value=0, decoded_calls=calls, simulation=None)
        self.assertIn("Target: 0xTarget", result)
        self.assertIn("pause()", result)
        self.assertIn("DeFi risk analyst", result)

    def test_with_protocol_and_label(self) -> None:
        calls = [DecodedCall(function_name="pause", signature="pause()")]
        result = _build_prompt(
            target="0xTarget",
            value=0,
            decoded_calls=calls,
            simulation=None,
            protocol="AAVE",
            label="Aave Governance V3",
        )
        self.assertIn("Protocol: AAVE", result)
        self.assertIn("Contract: Aave Governance V3", result)

    def test_with_eth_value(self) -> None:
        calls = [DecodedCall(function_name="transfer", signature="transfer(address,uint256)")]
        result = _build_prompt(target="0xTarget", value=int(1e18), decoded_calls=calls, simulation=None)
        self.assertIn("ETH Value:", result)

    def test_with_simulation(self) -> None:
        calls = [DecodedCall(function_name="pause", signature="pause()")]
        sim = SimulationResult(success=True, gas_used=50000)
        result = _build_prompt(target="0xTarget", value=0, decoded_calls=calls, simulation=sim)
        self.assertIn("Simulation Results", result)
        self.assertIn("SUCCESS", result)


class TestExplainTransaction(unittest.TestCase):
    """Tests for explain_transaction."""

    def test_empty_calldata_returns_none(self) -> None:
        result = explain_transaction(target="0xTarget", calldata="0x", chain_id=1)
        self.assertIsNone(result)

    def test_short_calldata_returns_none(self) -> None:
        result = explain_transaction(target="0xTarget", calldata="0x1234", chain_id=1)
        self.assertIsNone(result)

    @patch("utils.ai_explainer.get_llm_provider")
    @patch("utils.ai_explainer.simulate_transaction")
    @patch("utils.ai_explainer.decode_calldata")
    def test_successful_explanation(
        self,
        mock_decode: MagicMock,
        mock_simulate: MagicMock,
        mock_get_provider: MagicMock,
    ) -> None:
        mock_decode.return_value = DecodedCall(function_name="pause", signature="pause()")
        mock_simulate.return_value = SimulationResult(success=True, gas_used=50000)
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "This pauses the protocol."
        mock_provider.model_name = "test-model"
        mock_get_provider.return_value = mock_provider

        result = explain_transaction(
            target="0xTarget",
            calldata="0x8456cb59",  # pause()
            chain_id=1,
            protocol="AAVE",
        )

        self.assertEqual(result, "This pauses the protocol.")
        mock_simulate.assert_called_once()
        mock_provider.complete.assert_called_once()

    @patch("utils.ai_explainer.get_llm_provider")
    @patch("utils.ai_explainer.simulate_transaction")
    @patch("utils.ai_explainer.decode_calldata")
    def test_llm_error_returns_none(
        self,
        mock_decode: MagicMock,
        mock_simulate: MagicMock,
        mock_get_provider: MagicMock,
    ) -> None:
        mock_decode.return_value = DecodedCall(function_name="pause", signature="pause()")
        mock_simulate.return_value = None
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = LLMError("API error")
        mock_get_provider.return_value = mock_provider

        result = explain_transaction(target="0xTarget", calldata="0x8456cb59", chain_id=1)
        self.assertIsNone(result)

    @patch("utils.ai_explainer.decode_calldata")
    def test_undecoded_calldata_returns_none(self, mock_decode: MagicMock) -> None:
        mock_decode.return_value = None
        result = explain_transaction(target="0xTarget", calldata="0x11223344", chain_id=1)
        self.assertIsNone(result)

    @patch("utils.ai_explainer.get_llm_provider")
    @patch("utils.ai_explainer.simulate_transaction")
    @patch("utils.ai_explainer.decode_calldata")
    def test_simulation_failure_still_explains(
        self,
        mock_decode: MagicMock,
        mock_simulate: MagicMock,
        mock_get_provider: MagicMock,
    ) -> None:
        """If simulation fails, should still explain using decoded calldata only."""
        mock_decode.return_value = DecodedCall(function_name="pause", signature="pause()")
        mock_simulate.return_value = None  # Simulation failed
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "This pauses the protocol."
        mock_provider.model_name = "test-model"
        mock_get_provider.return_value = mock_provider

        result = explain_transaction(target="0xTarget", calldata="0x8456cb59", chain_id=1)
        self.assertEqual(result, "This pauses the protocol.")


class TestFormatExplanationLine(unittest.TestCase):
    """Tests for format_explanation_line."""

    def test_format(self) -> None:
        result = format_explanation_line("This pauses the protocol.")
        self.assertIn("AI Summary", result)
        self.assertIn("This pauses the protocol.", result)


if __name__ == "__main__":
    unittest.main()
