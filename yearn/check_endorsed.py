#!/usr/bin/env python3
"""Verify Yearn v3 yDaemon vaults are endorsed on-chain in the registry.

Fetches vault metadata from yDaemon per chain and checks each address via
the registry contract's isEndorsed function. Sends a Telegram alert if any
vaults are not endorsed.
"""

import os
from typing import Dict, List

import requests
from dotenv import load_dotenv
from web3 import Web3

from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

load_dotenv()

logger = get_logger("yearn.check_endorsed")

PROTOCOL = "yearn"

YDAEMON_BASE_URL = "https://ydaemon.yearn.fi/vaults/v3"
YDAEMON_PARAMS = "hideAlways=true&strategiesDetails=withDetails&strategiesCondition=inQueue"

REGISTRY_ADDRESS = Web3.to_checksum_address("0xd40ecF29e001c76Dcc4cC0D9cd50520CE845B038")
REGISTRY_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "isEndorsed",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    }
]

CHAINS = [Chain.MAINNET, Chain.POLYGON, Chain.BASE, Chain.ARBITRUM, Chain.KATANA]


def fetch_ydaemon_vaults(chain: Chain) -> List[str]:
    """Fetch vault addresses from yDaemon API for a given chain.

    Args:
        chain: The chain to fetch vaults for.

    Returns:
        List of vault addresses.
    """
    url = f"{YDAEMON_BASE_URL}?{YDAEMON_PARAMS}&chainIDs={chain.chain_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    vaults = response.json()
    return [vault["address"] for vault in vaults if "address" in vault]


def check_endorsed_for_chain(chain: Chain, addresses: List[str]) -> List[str]:
    """Check which yDaemon vaults are not endorsed on-chain for a given chain.

    Args:
        chain: The chain to check.
        addresses: List of vault addresses from yDaemon.

    Returns:
        List of unendorsed vault addresses.
    """
    client = ChainManager.get_client(chain)
    registry = client.get_contract(REGISTRY_ADDRESS, REGISTRY_ABI)

    unendorsed = []
    for address in addresses:
        try:
            checksum = Web3.to_checksum_address(address)
            endorsed = registry.functions.isEndorsed(checksum).call()
            if not endorsed:
                logger.warning("Not endorsed on %s: %s", chain.name, address)
                unendorsed.append(address)
        except Exception as e:
            logger.error("Error checking %s on %s: %s", address, chain.name, e)
            unendorsed.append(address)

    logger.info("Chain %s: %d/%d unendorsed", chain.name, len(unendorsed), len(addresses))
    return unendorsed


def build_alert_message(errors: Dict[Chain, List[str]], total_checked: int) -> str:
    """Build a Telegram alert message from the errors dict.

    Args:
        errors: Mapping of chain to list of unendorsed addresses.
        total_checked: Total number of vaults checked.

    Returns:
        Formatted alert message string.
    """
    total_errors = sum(len(addrs) for addrs in errors.values())
    lines = [
        "*yDaemon Endorsed Check*",
        f"Checked {total_checked} vaults, found {total_errors} unendorsed:\n",
    ]
    for chain, addresses in errors.items():
        lines.append(f"*{chain.name}* ({len(addresses)}):")
        for addr in addresses:
            lines.append(f"  `{addr}`")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Run the endorsed vault check across all configured chains."""
    logger.info("Starting yDaemon endorsed vault check")

    all_errors: Dict[Chain, List[str]] = {}
    total_checked = 0

    for chain in CHAINS:
        logger.info("Checking chain %s (id=%d)", chain.name, chain.chain_id)
        try:
            addresses = fetch_ydaemon_vaults(chain)
        except requests.RequestException as e:
            logger.error("Failed to fetch yDaemon data for %s: %s", chain.name, e)
            continue

        if not addresses:
            logger.info("No vaults found for %s, skipping", chain.name)
            continue

        logger.info("Found %d vaults for %s", len(addresses), chain.name)
        total_checked += len(addresses)

        unendorsed = check_endorsed_for_chain(chain, addresses)
        if unendorsed:
            all_errors[chain] = unendorsed

    total_errors = sum(len(addrs) for addrs in all_errors.values())
    logger.info("Done. %d/%d vaults unendorsed", total_errors, total_checked)

    if not all_errors:
        logger.info("All vaults endorsed, no alert needed")
        return

    message = build_alert_message(all_errors, total_checked)

    # If the message is too long for Telegram, send a short summary with a link to the logs
    max_length = 2000
    if len(message) > max_length:
        run_url = os.getenv("GITHUB_RUN_URL", "")
        if not run_url:
            server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
            repo = os.getenv("GITHUB_REPOSITORY", "")
            run_id = os.getenv("GITHUB_RUN_ID", "")
            if repo and run_id:
                run_url = f"{server}/{repo}/actions/runs/{run_id}"

        message = (
            f"*yDaemon Endorsed Check*\n"
            f"Found {total_errors} unendorsed vaults across {len(all_errors)} chains.\n"
            f"Too many to list here."
        )
        if run_url:
            message += f"\n[Check the full logs]({run_url})"

    send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    main()
