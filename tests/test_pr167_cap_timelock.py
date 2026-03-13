#!/usr/bin/env python3
"""Manual integration test for PR #167: AI-powered transaction explanations.

Tests the full pipeline using a real CAP TimelockController transaction:
  Tx: 0x18384fae0283d8b33c8d1423e9d80e11385af5c440de0ca875143582a6b46692
  Chain: Mainnet (1)
  3 calls to grantAccess(bytes4,address,address)

Usage:
    # Step 1: Calldata decoding only (no API keys needed)
    python tests/test_pr167_cap_timelock.py --decode-only

    # Step 2: + Tenderly simulation (needs TENDERLY_API_KEY)
    python tests/test_pr167_cap_timelock.py --simulate

    # Step 3: Full pipeline with LLM (needs TENDERLY_API_KEY + LLM_API_KEY)
    python tests/test_pr167_cap_timelock.py --full

    # Step 4: Full alert message build (same as --full but shows formatted Telegram message)
    python tests/test_pr167_cap_timelock.py --alert
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from eth_abi import encode
from web3 import Web3

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ---------------------------------------------------------------------------
# Test data from the real CAP timelock transaction
# ---------------------------------------------------------------------------
TX_HASH = "0x18384fae0283d8b33c8d1423e9d80e11385af5c440de0ca875143582a6b46692"
TARGET = "0x7731129a10d51e18cde607c5c115f26503d2c683"
TIMELOCK_ADDR = "0xd8236031d8279d82e615af2bfab5fc0127a329ab"
CHAIN_ID = 1
PROTOCOL = "CAP"
LABEL = "CAP TimelockController"
OPERATION_ID = "0xfake_op_id_for_testing"

# The 3 grantAccess calls from the transaction
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


def _build_calldata(call: dict) -> str:
    """Construct ABI-encoded calldata for grantAccess(bytes4,address,address)."""
    selector = Web3.keccak(text="grantAccess(bytes4,address,address)")[:4]
    encoded = encode(
        ["bytes4", "address", "address"],
        [bytes.fromhex(call["bytes4"]), call["addr1"], call["addr2"]],
    )
    return "0x" + selector.hex() + encoded.hex()


def _build_envio_events() -> list[dict]:
    """Build mock Envio GraphQL events matching this CAP transaction."""
    events = []
    for i, call in enumerate(GRANT_ACCESS_CALLS):
        events.append(
            {
                "id": f"test-event-{i}",
                "timelockAddress": TIMELOCK_ADDR,
                "timelockType": "TimelockController",
                "eventName": "CallScheduled",
                "chainId": CHAIN_ID,
                "blockNumber": 21000000,
                "blockTimestamp": 1710000000,
                "transactionHash": TX_HASH,
                "operationId": OPERATION_ID,
                "index": i,
                "target": TARGET,
                "value": "0",
                "data": _build_calldata(call),
                "predecessor": None,
                "delay": 86400,  # 1 day
                "signature": None,
                "creator": None,
                "metadata": None,
                "votesFor": None,
                "votesAgainst": None,
            }
        )
    return events


def test_calldata_encoding() -> None:
    """Verify we can build the calldata correctly."""
    print("=" * 60)
    print("STEP 1: Calldata Encoding")
    print("=" * 60)

    for i, call in enumerate(GRANT_ACCESS_CALLS):
        calldata = _build_calldata(call)
        selector = calldata[:10]
        print(f"\nCall {i}:")
        print(f"  Selector: {selector}")
        print(f"  Calldata length: {len(calldata)} chars ({(len(calldata) - 2) // 2} bytes)")
        print(f"  bytes4 param: 0x{call['bytes4']}")
        print(f"  Full calldata: {calldata[:50]}...")


def test_calldata_decoding() -> None:
    """Test that calldata_decoder can decode these calls."""
    from timelock.calldata_decoder import decode_calldata

    print("\n" + "=" * 60)
    print("STEP 2: Calldata Decoding")
    print("=" * 60)

    for i, call in enumerate(GRANT_ACCESS_CALLS):
        calldata = _build_calldata(call)
        decoded = decode_calldata(calldata)
        print(f"\nCall {i}:")
        if decoded:
            print(f"  Function: {decoded.signature}")
            for type_str, value in decoded.params:
                if isinstance(value, bytes):
                    print(f"  {type_str}: 0x{value.hex()}")
                else:
                    print(f"  {type_str}: {value}")
            print("  [OK] Decoded successfully")
        else:
            print(f"  [WARN] Could not decode calldata (selector: {calldata[:10]})")
            print("  This is expected if grantAccess is not in known_selectors")
            print("  and the 4byte API doesn't have it. The AI explainer will skip this call.")


def test_tenderly_simulation() -> None:
    """Test Tenderly simulation for each call."""
    from utils.tenderly.simulation import simulate_transaction

    print("\n" + "=" * 60)
    print("STEP 3: Tenderly Simulation")
    print("=" * 60)

    api_key = os.getenv("TENDERLY_API_KEY")
    if not api_key:
        print("\n  [SKIP] TENDERLY_API_KEY not set")
        return

    for i, call in enumerate(GRANT_ACCESS_CALLS):
        calldata = _build_calldata(call)
        print(f"\nSimulating Call {i} (grantAccess with bytes4=0x{call['bytes4']})...")

        result = simulate_transaction(
            target=TARGET,
            calldata=calldata,
            chain_id=CHAIN_ID,
            value=0,
            from_address=TIMELOCK_ADDR,
        )

        if result:
            print(f"  Success: {result.success}")
            print(f"  Gas used: {result.gas_used:,}")
            if result.error_message:
                print(f"  Error: {result.error_message}")
            if result.state_changes:
                print(f"  State changes: {len(result.state_changes)}")
                for sc in result.state_changes[:3]:
                    print(f"    {sc.contract_address}: {sc.key}")
            if result.asset_changes:
                print(f"  Asset changes: {len(result.asset_changes)}")
            if result.logs:
                print(f"  Events emitted: {len(result.logs)}")
            print("  [OK] Simulation completed")
        else:
            print("  [WARN] Simulation returned None (API error or no data)")


def test_llm_explanation() -> None:
    """Test LLM explanation for the batch transaction."""
    from utils.llm.ai_explainer import explain_batch_transaction, explain_transaction

    print("\n" + "=" * 60)
    print("STEP 4: LLM Explanation")
    print("=" * 60)

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("\n  [SKIP] LLM_API_KEY not set")
        return

    provider_name = os.getenv("LLM_PROVIDER", "venice")
    model = os.getenv("LLM_MODEL", "")
    print(f"\n  Provider: {provider_name}")
    if model:
        print(f"  Model: {model}")

    # Test single call explanation
    print("\n--- Single call (Call 0) ---")
    calldata = _build_calldata(GRANT_ACCESS_CALLS[0])
    single_result = explain_transaction(
        target=TARGET,
        calldata=calldata,
        chain_id=CHAIN_ID,
        value=0,
        protocol=PROTOCOL,
        label=LABEL,
        from_address=TIMELOCK_ADDR,
    )
    if single_result:
        print(f"  [OK] Explanation:\n  {single_result}")
    else:
        print("  [WARN] No explanation returned (calldata may not have decoded)")

    # Test batch explanation (all 3 calls)
    print("\n--- Batch (all 3 calls) ---")
    calls = []
    for call in GRANT_ACCESS_CALLS:
        calls.append({"target": TARGET, "data": _build_calldata(call), "value": "0"})

    batch_result = explain_batch_transaction(
        calls=calls,
        chain_id=CHAIN_ID,
        protocol=PROTOCOL,
        label=LABEL,
        from_address=TIMELOCK_ADDR,
    )
    if batch_result:
        print(f"  [OK] Batch explanation:\n  {batch_result}")
    else:
        print("  [WARN] No batch explanation returned")


def test_full_alert_message() -> None:
    """Test building the complete Telegram alert message."""
    from timelock.timelock_alerts import TimelockConfig, build_alert_message

    print("\n" + "=" * 60)
    print("STEP 5: Full Alert Message")
    print("=" * 60)

    events = _build_envio_events()
    timelock_config = TimelockConfig(
        address=TIMELOCK_ADDR,
        chain_id=CHAIN_ID,
        protocol=PROTOCOL,
        label=LABEL,
    )

    message = build_alert_message(events, timelock_config)

    print("\n--- Telegram Message Preview ---")
    print(message)
    print("--- End of Message ---")
    print(f"\n  Message length: {len(message)} chars (max: 4096)")
    if len(message) > 4096:
        print("  [WARN] Message exceeds Telegram limit!")
    else:
        print("  [OK] Message fits within Telegram limit")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual integration test for PR #167")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--decode-only", action="store_true", help="Only test calldata encoding/decoding (no API keys)")
    group.add_argument("--simulate", action="store_true", help="Test decoding + Tenderly simulation")
    group.add_argument("--full", action="store_true", help="Test full pipeline: decode + simulate + LLM")
    group.add_argument(
        "--alert", action="store_true", help="Test full alert message build (decode + simulate + LLM + formatting)"
    )
    args = parser.parse_args()

    print(f"Testing with CAP TimelockController tx: {TX_HASH}")
    print(f"Chain: Mainnet ({CHAIN_ID}), Protocol: {PROTOCOL}")
    print(f"Target: {TARGET}")
    print(f"Timelock: {TIMELOCK_ADDR}")

    test_calldata_encoding()
    test_calldata_decoding()

    if args.simulate or args.full or args.alert:
        test_tenderly_simulation()

    if args.full or args.alert:
        test_llm_explanation()

    if args.alert:
        test_full_alert_message()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
