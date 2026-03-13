#!/usr/bin/env python3
"""Compare AI summaries across different LLM models for the CAP timelock tx.

Caches Tenderly simulation results to disk so only the LLM call varies between runs.

Usage:
    # First run (simulates + caches + calls LLM):
    python tests/test_pr167_model_compare.py

    # Switch model via env var:
    LLM_MODEL=zai-org-glm-5 python tests/test_pr167_model_compare.py
    LLM_MODEL=grok-41-fast python tests/test_pr167_model_compare.py

    # Switch provider:
    LLM_PROVIDER=anthropic LLM_MODEL=claude-haiku-4-5-20251001 python tests/test_pr167_model_compare.py

    # Force re-simulate (ignore cache):
    python tests/test_pr167_model_compare.py --no-cache
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from eth_abi import encode
from web3 import Web3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
TARGET = "0x7731129a10d51e18cde607c5c115f26503d2c683"
TIMELOCK_ADDR = "0xd8236031d8279d82e615af2bfab5fc0127a329ab"
CHAIN_ID = 1
PROTOCOL = "CAP"
LABEL = "CAP TimelockController"

GRANT_ACCESS_CALLS = [
    {
        "bytes4": "f6be71d1",
        "addr1": "0xa1a20aBdc873CF291c22Ce3C8968EC06277324D0",
        "addr2": "0xD8236031d8279d82E615aF2BFab5FC0127A329ab",
    },
    {
        "bytes4": "75bb23e8",
        "addr1": "0xa1a20aBdc873CF291c22Ce3C8968EC06277324D0",
        "addr2": "0xD8236031d8279d82E615aF2BFab5FC0127A329ab",
    },
    {
        "bytes4": "17d86154",
        "addr1": "0xa1a20aBdc873CF291c22Ce3C8968EC06277324D0",
        "addr2": "0xD8236031d8279d82E615aF2BFab5FC0127A329ab",
    },
]

CACHE_FILE = Path(__file__).parent / "fixtures" / "cap_timelock_simulations.json"


def _build_calldata(call: dict) -> str:
    selector = Web3.keccak(text="grantAccess(bytes4,address,address)")[:4]
    encoded = encode(
        ["bytes4", "address", "address"],
        [bytes.fromhex(call["bytes4"]), call["addr1"], call["addr2"]],
    )
    return "0x" + selector.hex() + encoded.hex()


def _simulate_and_cache() -> list[dict | None]:
    """Run Tenderly simulations and cache raw responses to disk."""
    from utils.tenderly.simulation import simulate_transaction

    results: list[dict | None] = []
    for i, call in enumerate(GRANT_ACCESS_CALLS):
        calldata = _build_calldata(call)
        print(f"  Simulating call {i} (bytes4=0x{call['bytes4']})...")
        sim = simulate_transaction(
            target=TARGET, calldata=calldata, chain_id=CHAIN_ID, value=0, from_address=TIMELOCK_ADDR
        )
        results.append(sim.raw_response if sim else None)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(results, indent=2))
    print(f"  Cached to {CACHE_FILE}")
    return results


def _load_cached_simulations() -> list[dict | None]:
    """Load cached Tenderly responses from disk."""
    if not CACHE_FILE.exists():
        return []
    return json.loads(CACHE_FILE.read_text())


def _raw_to_simulation_result(raw: dict | None):
    """Convert raw Tenderly JSON to SimulationResult."""
    if not raw:
        return None
    from utils.tenderly.simulation import SimulationResult, _parse_asset_changes, _parse_state_changes

    tx = raw.get("transaction", {})
    tx_info = tx.get("transaction_info", {})
    success = tx.get("status", False)
    gas_used = int(tx_info.get("gas_used", 0))
    error_message = tx_info.get("stack_trace", [{}])[0].get("error_reason", "") if not success else ""
    asset_changes = _parse_asset_changes(tx_info.get("asset_changes", []) or [])
    state_changes = _parse_state_changes(tx_info.get("state_diff", []) or [])
    logs = tx_info.get("logs", []) or []

    return SimulationResult(
        success=success,
        gas_used=gas_used,
        asset_changes=asset_changes,
        state_changes=state_changes,
        logs=logs,
        error_message=error_message,
        raw_response=raw,
    )


def run_explanation(cached_sims: list[dict | None]) -> str | None:
    """Run LLM explanation using cached simulation data."""
    from timelock.calldata_decoder import decode_calldata
    from utils.llm import get_llm_provider
    from utils.llm.ai_explainer import _build_prompt
    from utils.llm.factory import reset_provider

    # Reset singleton so env var changes take effect
    reset_provider()

    # Decode all calls
    decoded_calls = []
    for call in GRANT_ACCESS_CALLS:
        calldata = _build_calldata(call)
        decoded = decode_calldata(calldata)
        if decoded:
            decoded_calls.append(decoded)

    if not decoded_calls:
        print("  [ERROR] No calls could be decoded")
        return None

    # Use first successful simulation
    simulation = None
    for raw in cached_sims:
        sim = _raw_to_simulation_result(raw)
        if sim:
            simulation = sim
            break

    # Build prompt
    targets = ", ".join([TARGET] * len(GRANT_ACCESS_CALLS))
    prompt = _build_prompt(
        target=targets, value=0, decoded_calls=decoded_calls, simulation=simulation, protocol=PROTOCOL, label=LABEL
    )

    # Call LLM
    provider = get_llm_provider()
    print(f"  Provider: {provider.__class__.__name__}")
    print(f"  Model: {provider.model_name}")
    explanation = provider.complete(prompt)
    return explanation


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare LLM models for AI summary")
    parser.add_argument("--no-cache", action="store_true", help="Force re-simulate (ignore cached results)")
    args = parser.parse_args()

    # Step 1: Get simulations (cached or fresh)
    if args.no_cache or not CACHE_FILE.exists():
        print("Running Tenderly simulations...")
        cached_sims = _simulate_and_cache()
    else:
        print(f"Using cached simulations from {CACHE_FILE}")
        cached_sims = _load_cached_simulations()

    # Step 2: Run LLM explanation
    print("\nGenerating AI summary...")
    explanation = run_explanation(cached_sims)

    if explanation:
        provider_name = os.getenv("LLM_PROVIDER", "venice")
        model_name = os.getenv("LLM_MODEL", "")
        print(f"\n{'=' * 60}")
        print(f"Model: {provider_name}/{model_name}")
        print(f"{'=' * 60}")
        print(f"\n🤖 AI Summary:\n{explanation}")
        print(f"\n{'=' * 60}")
        print(f"Length: {len(explanation)} chars")
    else:
        print("\n  [ERROR] No explanation generated")


if __name__ == "__main__":
    main()
