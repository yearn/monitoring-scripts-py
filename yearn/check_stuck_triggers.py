#!/usr/bin/env python3
"""Monitor TKS triggers to detect when they've been stuck in 'true' state for >24 hours.

Queries CommonReportTrigger contract on-chain to check if strategies and vaults
have report/tend triggers that should be executed. Tracks trigger state over time
and alerts when a trigger has been stuck in the 'true' state for over a threshold
period (default 24 hours), which indicates potential keeper service issues.
"""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from web3 import Web3

from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message_with_fallback
from utils.web3_wrapper import ChainManager

load_dotenv()

logger = get_logger("yearn.check_stuck_triggers")

PROTOCOL = "yearn"

# yDaemon API configuration
YDAEMON_BASE_URL = "https://ydaemon.yearn.fi/vaults/v3"
YDAEMON_PARAMS = "hideAlways=true&strategiesDetails=withDetails&strategiesCondition=inQueue"

# CommonReportTrigger contract (same address on all chains)
COMMON_REPORT_TRIGGER = Web3.to_checksum_address("0xf8dF17a35c88AbB25e83C92f9D293B4368b9D52D")

# CommonReportTrigger ABI (only the functions we need)
COMMON_REPORT_TRIGGER_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "_strategy", "type": "address"}],
        "name": "strategyReportTrigger",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "_vault", "type": "address"},
            {"internalType": "address", "name": "_strategy", "type": "address"},
        ],
        "name": "vaultReportTrigger",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "_strategy", "type": "address"}],
        "name": "strategyTendTrigger",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "bytes", "name": "", "type": "bytes"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Default cache file location
DEFAULT_CACHE_FILE = "tks-trigger-cache.json"


@dataclass
class TriggerState:
    """Represents the state of a trigger at a point in time."""

    triggered: bool
    first_seen: datetime
    last_checked: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "triggered": self.triggered,
            "first_seen": self.first_seen.isoformat(),
            "last_checked": self.last_checked.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TriggerState":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            triggered=data["triggered"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_checked=datetime.fromisoformat(data["last_checked"]),
        )


@dataclass
class StuckTrigger:
    """Represents a trigger that has been stuck for too long."""

    chain: Chain
    trigger_type: str  # "strategy_report", "vault_report", "strategy_tend"
    strategy_address: str
    vault_address: Optional[str]  # Only for vault_report triggers
    hours_stuck: float
    reason: Optional[str] = None


def fetch_ydaemon_vaults(chain: Chain) -> List[dict]:
    """Fetch vault metadata from yDaemon API.

    Args:
        chain: The chain to fetch vaults for.

    Returns:
        List of vault objects with addresses and strategies.
    """
    url = f"{YDAEMON_BASE_URL}?{YDAEMON_PARAMS}&chainIDs={chain.chain_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_strategies_from_vaults(vaults: List[dict]) -> List[str]:
    """Extract unique strategy addresses from vault data.

    Args:
        vaults: List of vault objects from yDaemon.

    Returns:
        List of unique strategy addresses (lowercase).
    """
    strategies = set()
    for vault in vaults:
        if "strategies" in vault:
            for strategy in vault["strategies"]:
                if "address" in strategy:
                    strategies.add(strategy["address"].lower())
    return list(strategies)


def check_triggers_for_chain(
    chain: Chain, vaults: List[dict], standalone_strategies: Optional[List[str]] = None
) -> Dict[str, tuple[bool, str]]:
    """Check all triggers for a given chain using batch RPC calls.

    Args:
        chain: The chain to check triggers on.
        vaults: List of vault objects from yDaemon.
        standalone_strategies: Optional list of standalone strategy addresses to check.

    Returns:
        Dictionary mapping trigger keys to (triggered, reason) tuples.
        Key format: "{type}_{vault_addr}_{strategy_addr}" or "{type}_{strategy_addr}"
    """
    client = ChainManager.get_client(chain)
    trigger_contract = client.get_contract(COMMON_REPORT_TRIGGER, COMMON_REPORT_TRIGGER_ABI)

    results = {}

    with client.batch_requests() as batch:
        # Track what we're querying for result mapping
        query_map = []

        # Check vault report triggers (vault + strategy pairs)
        for vault in vaults:
            vault_addr = Web3.to_checksum_address(vault["address"])
            if "strategies" in vault:
                for strategy in vault["strategies"]:
                    strategy_addr = Web3.to_checksum_address(strategy["address"])
                    key = f"vault_report_{vault_addr.lower()}_{strategy_addr.lower()}"
                    batch.add(trigger_contract.functions.vaultReportTrigger(vault_addr, strategy_addr))
                    query_map.append(key)

        # Check standalone strategy report triggers
        if standalone_strategies:
            for strategy_addr in standalone_strategies:
                strategy_addr_checksum = Web3.to_checksum_address(strategy_addr)
                key = f"strategy_report_{strategy_addr}"
                batch.add(trigger_contract.functions.strategyReportTrigger(strategy_addr_checksum))
                query_map.append(key)

                # Also check tend triggers for standalone strategies
                key_tend = f"strategy_tend_{strategy_addr}"
                batch.add(trigger_contract.functions.strategyTendTrigger(strategy_addr_checksum))
                query_map.append(key_tend)

        # Execute all queries
        batch_results = batch.execute()

    # Map results back to trigger keys
    for key, result in zip(query_map, batch_results):
        triggered, data = result
        # Decode the reason if available
        reason = None
        if isinstance(data, bytes):
            try:
                reason = data.decode("utf-8") if data else None
            except UnicodeDecodeError:
                reason = data.hex() if data else None

        results[key] = (triggered, reason or "")

    return results


def load_trigger_cache(cache_file: Path) -> Dict[str, TriggerState]:
    """Load trigger state cache from JSON file.

    Args:
        cache_file: Path to the cache file.

    Returns:
        Dictionary mapping "{chain_id}_{trigger_key}" to TriggerState.
    """
    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            return {key: TriggerState.from_dict(value) for key, value in data.items()}
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("Failed to load cache file: %s. Starting fresh.", e)
        return {}


def save_trigger_cache(cache_file: Path, cache: Dict[str, TriggerState]) -> None:
    """Save trigger state cache to JSON file.

    Args:
        cache_file: Path to the cache file.
        cache: Dictionary mapping trigger keys to TriggerState.
    """
    with open(cache_file, "w") as f:
        json.dump({key: value.to_dict() for key, value in cache.items()}, f, indent=2)


def update_cache_with_current_state(
    cache: Dict[str, TriggerState],
    chain: Chain,
    current_triggers: Dict[str, tuple[bool, str]],
    now: datetime,
) -> None:
    """Update cache with current trigger states.

    Args:
        cache: The cache dictionary to update (modified in place).
        chain: The chain being checked.
        current_triggers: Current trigger states from on-chain queries.
        now: Current timestamp.
    """
    for trigger_key, (triggered, reason) in current_triggers.items():
        cache_key = f"{chain.chain_id}_{trigger_key}"

        if triggered:
            # Trigger is true
            if cache_key in cache and cache[cache_key].triggered:
                # Already was triggered, just update last_checked
                cache[cache_key].last_checked = now
            else:
                # Newly triggered, record first_seen
                cache[cache_key] = TriggerState(triggered=True, first_seen=now, last_checked=now)
        else:
            # Trigger is false, remove from cache if it exists
            if cache_key in cache:
                del cache[cache_key]


def identify_stuck_triggers(
    cache: Dict[str, TriggerState], threshold_hours: float, now: datetime, current_reasons: Dict[str, str]
) -> List[StuckTrigger]:
    """Identify triggers that have been stuck in 'true' state for too long.

    Args:
        cache: The cache dictionary with trigger states.
        threshold_hours: Minimum hours a trigger must be stuck to be reported.
        now: Current timestamp.
        current_reasons: Map of cache_key to current reason string from live on-chain queries.

    Returns:
        List of StuckTrigger objects.
    """
    stuck_triggers = []

    for cache_key, state in cache.items():
        time_stuck = now - state.first_seen
        hours_stuck = time_stuck.total_seconds() / 3600

        if hours_stuck >= threshold_hours:
            try:
                # Parse cache_key: "{chain_id}_{type}_{addresses}"
                parts = cache_key.split("_", 3)
                if len(parts) < 4:
                    logger.warning("Malformed cache key: %s", cache_key)
                    continue

                chain_id = int(parts[0])
                trigger_type = f"{parts[1]}_{parts[2]}"  # e.g., "vault_report", "strategy_report"

                chain = Chain.from_chain_id(chain_id)

                # Parse addresses based on trigger type
                if trigger_type == "vault_report":
                    # Format: vault_report_{vault_addr}_{strategy_addr}
                    remaining = parts[3]
                    addr_parts = remaining.split("_")
                    if len(addr_parts) < 2:
                        logger.warning("Malformed vault_report cache key: %s", cache_key)
                        continue
                    vault_address = addr_parts[0]
                    strategy_address = addr_parts[1]
                else:
                    # Format: strategy_report_{strategy_addr} or strategy_tend_{strategy_addr}
                    strategy_address = parts[3]
                    vault_address = None

                stuck_triggers.append(
                    StuckTrigger(
                        chain=chain,
                        trigger_type=trigger_type,
                        strategy_address=strategy_address,
                        vault_address=vault_address,
                        hours_stuck=hours_stuck,
                        reason=current_reasons.get(cache_key),
                    )
                )
            except (ValueError, IndexError) as e:
                logger.warning("Failed to parse cache key %s: %s", cache_key, e)
                continue

    return stuck_triggers


def build_alert_message(stuck_triggers: List[StuckTrigger], threshold_hours: float) -> str:
    """Build Telegram alert message for stuck triggers.

    Args:
        stuck_triggers: List of stuck triggers to report.
        threshold_hours: The threshold used (for message context).

    Returns:
        Formatted alert message.
    """
    # Group by chain
    by_chain: Dict[Chain, List[StuckTrigger]] = {}
    for trigger in stuck_triggers:
        if trigger.chain not in by_chain:
            by_chain[trigger.chain] = []
        by_chain[trigger.chain].append(trigger)

    lines = [
        "⚠️ *TKS Trigger Alert*",
        f"Found {len(stuck_triggers)} trigger(s) stuck for >{threshold_hours:.0f} hours\n",
    ]

    for chain in sorted(by_chain.keys(), key=lambda c: c.chain_id):
        triggers = by_chain[chain]
        lines.append(f"*{chain.name}* ({len(triggers)} trigger(s)):")

        for trigger in triggers:
            trigger_label = trigger.trigger_type.replace("_", " ").title()
            lines.append(f"  • {trigger_label}: stuck for {trigger.hours_stuck:.1f} hours")

            explorer_url = chain.explorer_url
            if trigger.vault_address:
                vault_url = f"{explorer_url}/address/{trigger.vault_address}"
                lines.append(f"    Vault: [{trigger.vault_address}]({vault_url})")

            strategy_url = f"{explorer_url}/address/{trigger.strategy_address}"
            lines.append(f"    Strategy: [{trigger.strategy_address}]({strategy_url})")

            if trigger.reason:
                lines.append(f"    Reason: `{trigger.reason}`")

        lines.append("")

    lines.append("🔍 *Possible causes:*")
    lines.append("  • Keeper service not executing")
    lines.append("  • Health check failures")
    lines.append("  • Gas prices too high")
    lines.append("  • Strategy configuration issues")

    return "\n".join(lines)


def main() -> None:
    """Main entry point for the stuck trigger monitoring script."""
    parser = argparse.ArgumentParser(description="Monitor TKS triggers for strategies/vaults stuck in 'true' state")
    parser.add_argument(
        "--threshold-hours",
        type=float,
        default=24.0,
        help="Minimum hours a trigger must be stuck to alert (default: 24.0)",
    )
    parser.add_argument(
        "--chains",
        type=str,
        default="MAINNET,POLYGON,BASE,ARBITRUM,KATANA",
        help="Comma-separated chain names to check (default: all supported)",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=DEFAULT_CACHE_FILE,
        help=f"Path to cache file (default: {DEFAULT_CACHE_FILE})",
    )
    parser.add_argument(
        "--include-strategies",
        type=str,
        default="",
        help="Comma-separated list of standalone strategy addresses to monitor",
    )

    args = parser.parse_args()

    # Parse chains
    chain_names = [name.strip() for name in args.chains.split(",")]
    chains_to_check = [Chain.from_name(name.lower()) for name in chain_names]

    # Parse standalone strategies
    standalone_strategies = []
    if args.include_strategies:
        standalone_strategies = [addr.strip().lower() for addr in args.include_strategies.split(",")]

    cache_file = Path(args.cache_file)
    now = datetime.now(timezone.utc)

    logger.info("Starting TKS trigger monitoring (threshold: %.1f hours)", args.threshold_hours)

    # Load existing cache
    cache = load_trigger_cache(cache_file)
    logger.info("Loaded %d cached trigger states", len(cache))

    # Check each chain
    current_reasons: Dict[str, str] = {}
    for chain in chains_to_check:
        logger.info("Checking chain %s (id=%d)", chain.name, chain.chain_id)

        try:
            # Fetch vault data from yDaemon
            vaults = fetch_ydaemon_vaults(chain)
            logger.info("Found %d vaults for %s", len(vaults), chain.name)

            # Extract strategies from vaults
            vault_strategies = extract_strategies_from_vaults(vaults)
            logger.info("Found %d strategies in vaults for %s", len(vault_strategies), chain.name)

            # Only include standalone strategies that are NOT already in vaults
            # (vault strategies get checked via vaultReportTrigger, not standalone triggers)
            vault_strategy_set = set(vault_strategies)
            truly_standalone = [s for s in standalone_strategies if s not in vault_strategy_set]
            logger.info("Found %d standalone strategies for %s", len(truly_standalone), chain.name)

            # Check all triggers on-chain
            current_triggers = check_triggers_for_chain(chain, vaults, truly_standalone)
            logger.info("Checked %d triggers for %s", len(current_triggers), chain.name)

            # Update cache with current state
            update_cache_with_current_state(cache, chain, current_triggers, now)

            # Collect reasons keyed by full cache key for use in alert
            for trigger_key, (triggered, reason) in current_triggers.items():
                if triggered and reason:
                    current_reasons[f"{chain.chain_id}_{trigger_key}"] = reason

        except requests.RequestException as e:
            logger.error("Failed to fetch yDaemon data for %s: %s", chain.name, e)
            continue
        except Exception as e:
            logger.error("Error checking triggers for %s: %s", chain.name, e, exc_info=True)
            continue

    # Save updated cache
    save_trigger_cache(cache_file, cache)
    logger.info("Saved %d trigger states to cache", len(cache))

    # Identify stuck triggers
    stuck_triggers = identify_stuck_triggers(cache, args.threshold_hours, now, current_reasons)
    logger.info("Found %d stuck triggers", len(stuck_triggers))

    if not stuck_triggers:
        logger.info("No stuck triggers found, no alert needed")
        return

    # Build and send alert
    message = build_alert_message(stuck_triggers, args.threshold_hours)

    fallback = (
        f"⚠️ *TKS Trigger Alert*\n"
        f"Found {len(stuck_triggers)} trigger(s) stuck for >{args.threshold_hours:.0f} hours.\n"
        f"Too many to list here."
    )
    send_telegram_message_with_fallback(message, PROTOCOL, fallback)
    logger.info("Alert sent successfully")


if __name__ == "__main__":
    main()
