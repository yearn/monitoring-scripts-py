#!/usr/bin/env python3
"""Monitor large iUSD mints via totalSupply delta only (no event scanning)."""

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

PROTOCOL = "infinifi"
logger = get_logger(f"{PROTOCOL}.large_mints")

IUSD_TOKEN_ADDR = Web3.to_checksum_address("0x48f9e38f3070AD8945DFEae3FA70987722E3D89c")

MINT_THRESHOLD_PERCENT = Decimal(Config.get_env("IUSD_LARGE_MINT_THRESHOLD_PERCENT", "0.05"))

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
    threshold_tokens = _format_units(int(previous_raw * MINT_THRESHOLD_PERCENT), decimals)
    threshold_percent_display = MINT_THRESHOLD_PERCENT * Decimal(100)

    msg = (
        "*iUSD Large Mint Alert (Supply Delta)*\n\n"
        f"Threshold: {threshold_percent_display:,.2f}% of totalSupply "
        f"(~{threshold_tokens:,.2f} iUSD at previous supply)\n"
        f"Supply increase: {delta:,.2f} iUSD\n"
        f"Previous totalSupply: {previous:,.2f}\n"
        f"Current totalSupply: {current:,.2f}\n\n"
        "This monitor intentionally uses only totalSupply deltas (no event scanning)."
    )
    send_alert(Alert(AlertSeverity.LOW, msg, PROTOCOL))


def main() -> None:
    client = ChainManager.get_client(Chain.MAINNET)
    erc20_abi = load_abi("common-abi/ERC20.json")
    iusd = client.get_contract(IUSD_TOKEN_ADDR, erc20_abi)

    try:
        with client.batch_requests() as batch:
            batch.add(iusd.functions.decimals())
            batch.add(iusd.functions.totalSupply())
            decimals, current_supply_raw = client.execute_batch(batch)

        decimals = int(decimals)
        current_supply_raw = int(current_supply_raw)

        last_supply_cached = _to_int(get_last_value_for_key_from_file(cache_filename, CACHE_KEY_LAST_SUPPLY))
        if last_supply_cached > 0:
            delta_raw = current_supply_raw - last_supply_cached
            threshold_raw = int(last_supply_cached * MINT_THRESHOLD_PERCENT)
            if delta_raw >= threshold_raw:
                _send_large_supply_increase_alert(
                    delta_raw=delta_raw,
                    previous_raw=last_supply_cached,
                    current_raw=current_supply_raw,
                    decimals=decimals,
                )

        write_last_value_to_file(cache_filename, CACHE_KEY_LAST_SUPPLY, current_supply_raw)

    except Exception as exc:
        logger.error("iUSD large mint monitoring failed: %s", exc)
        send_alert(Alert(AlertSeverity.LOW, f"iUSD large mint monitor failed: {exc}", PROTOCOL), plain_text=True)


if __name__ == "__main__":
    main()
