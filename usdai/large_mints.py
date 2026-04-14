#!/usr/bin/env python3
"""Monitor large USDai mints via totalSupply delta only (no event scanning)."""

from decimal import Decimal, getcontext

from web3 import Web3

from utils.abi import load_abi
from utils.alert import Alert, AlertSeverity, send_alert
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.config import Config
from utils.logging import get_logger
from utils.web3_wrapper import ChainManager

getcontext().prec = 40

PROTOCOL = "usdai"
logger = get_logger(f"{PROTOCOL}.large_mints")

USDAI_TOKEN_ADDR = Web3.to_checksum_address("0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF")

MINT_THRESHOLD_TOKENS = Decimal(Config.get_env("USDAI_LARGE_MINT_THRESHOLD", "100000"))

CACHE_KEY_LAST_BLOCK = f"{PROTOCOL}_large_mints_last_block"
CACHE_KEY_LAST_SUPPLY = f"{PROTOCOL}_large_mints_last_supply"


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_units(raw_value: int, decimals: int) -> Decimal:
    return Decimal(raw_value) / (Decimal(10) ** decimals)


def _send_large_supply_increase_alert(delta_raw: int, previous_raw: int, current_raw: int, decimals: int) -> None:
    delta = _format_units(delta_raw, decimals)
    previous = _format_units(previous_raw, decimals)
    current = _format_units(current_raw, decimals)

    msg = (
        "*USDai Large Mint Alert (Supply Delta)*\n\n"
        f"Threshold: {MINT_THRESHOLD_TOKENS:,.0f} USDai\n"
        f"Supply increase: {delta:,.2f} USDai\n"
        f"Previous totalSupply: {previous:,.2f}\n"
        f"Current totalSupply: {current:,.2f}\n\n"
        "This monitor intentionally uses only totalSupply deltas (no event scanning)."
    )
    send_alert(Alert(AlertSeverity.MEDIUM, msg, PROTOCOL))


def main() -> None:
    client = ChainManager.get_client(Chain.ARBITRUM)
    erc20_abi = load_abi("common-abi/ERC20.json")
    usdai = client.get_contract(USDAI_TOKEN_ADDR, erc20_abi)

    try:
        decimals = int(usdai.functions.decimals().call())
        threshold_raw = int(MINT_THRESHOLD_TOKENS * (Decimal(10) ** decimals))

        latest_block = int(client.eth.block_number)
        current_supply_raw = int(usdai.functions.totalSupply().call())

        last_supply_cached = _to_int(get_last_value_for_key_from_file(cache_filename, CACHE_KEY_LAST_SUPPLY))
        if last_supply_cached > 0:
            delta_raw = current_supply_raw - last_supply_cached
            if delta_raw >= threshold_raw:
                _send_large_supply_increase_alert(
                    delta_raw=delta_raw,
                    previous_raw=last_supply_cached,
                    current_raw=current_supply_raw,
                    decimals=decimals,
                )

        write_last_value_to_file(cache_filename, CACHE_KEY_LAST_SUPPLY, current_supply_raw)
        write_last_value_to_file(cache_filename, CACHE_KEY_LAST_BLOCK, latest_block)

    except Exception as exc:
        logger.error("USDai large mint monitoring failed: %s", exc)
        send_alert(Alert(AlertSeverity.MEDIUM, f"USDai large mint monitor failed: {exc}", PROTOCOL), plain_text=True)


if __name__ == "__main__":
    main()
