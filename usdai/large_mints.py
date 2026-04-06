#!/usr/bin/env python3
"""Monitor large USDai mints on Arbitrum with event and supply-delta checks."""

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
CONFIRMATIONS = Config.get_env_int("USDAI_MINT_CONFIRMATIONS", 10)
INITIAL_LOOKBACK_BLOCKS = Config.get_env_int("USDAI_MINT_INITIAL_LOOKBACK_BLOCKS", 3000)
LOG_CHUNK_SIZE = Config.get_env_int("USDAI_MINT_LOG_CHUNK_SIZE", 2000)
MAX_LINES_IN_ALERT = Config.get_env_int("USDAI_MINT_MAX_LINES_IN_ALERT", 10)

CACHE_KEY_LAST_BLOCK = f"{PROTOCOL}_large_mints_last_block"
CACHE_KEY_LAST_SUPPLY = f"{PROTOCOL}_large_mints_last_supply"

TRANSFER_TOPIC0 = "0x" + Web3.keccak(text="Transfer(address,address,uint256)").hex()
ZERO_TOPIC = "0x" + "0" * 64


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_units(raw_value: int, decimals: int) -> Decimal:
    return Decimal(raw_value) / (Decimal(10) ** decimals)


def _extract_topic_address(topic) -> str:
    topic_hex = topic.hex() if hasattr(topic, "hex") else str(topic)
    return Web3.to_checksum_address("0x" + topic_hex[-40:])


def _fetch_mint_logs(client, from_block: int, to_block: int) -> list:
    logs = []
    if from_block > to_block:
        return logs

    for start in range(from_block, to_block + 1, LOG_CHUNK_SIZE):
        end = min(start + LOG_CHUNK_SIZE - 1, to_block)
        params = {
            "address": USDAI_TOKEN_ADDR,
            "fromBlock": start,
            "toBlock": end,
            "topics": [TRANSFER_TOPIC0, ZERO_TOPIC],
        }
        chunk_logs = client.eth.get_logs(params)
        logs.extend(chunk_logs)

    return logs


def _send_large_mints_alert(entries: list[dict], decimals: int, from_block: int, to_block: int) -> None:
    explorer = Chain.ARBITRUM.explorer_url
    lines = [
        "*USDai Large Mint Alert*",
        f"Window: blocks {from_block:,} - {to_block:,}",
        f"Threshold: {MINT_THRESHOLD_TOKENS:,.0f} USDai",
        f"Detected: {len(entries)} large mint(s)",
        "",
    ]

    for entry in entries[:MAX_LINES_IN_ALERT]:
        amount = _format_units(entry["amount_raw"], decimals)
        tx_hash = entry["tx_hash"]
        recipient = entry["to"]
        tx_line = f"[{tx_hash}]({explorer}/tx/{tx_hash})" if explorer else tx_hash
        recipient_line = f"[{recipient}]({explorer}/address/{recipient})" if explorer else recipient
        lines.append(f"- {amount:,.2f} USDai -> {recipient_line} | block {entry['block_number']} | tx {tx_line}")

    extra_count = len(entries) - MAX_LINES_IN_ALERT
    if extra_count > 0:
        lines.append(f"- ...and {extra_count} more")

    send_alert(Alert(AlertSeverity.MEDIUM, "\n".join(lines), PROTOCOL))


def _send_unexplained_supply_jump_alert(
    supply_delta_raw: int, mint_events_total_raw: int, decimals: int, from_block: int, to_block: int
) -> None:
    supply_delta = _format_units(supply_delta_raw, decimals)
    mint_events_total = _format_units(mint_events_total_raw, decimals)
    unexplained = _format_units(max(supply_delta_raw - mint_events_total_raw, 0), decimals)

    msg = (
        "*USDai Supply Jump (No Matching Mint Events)*\n\n"
        f"Window: blocks {from_block:,} - {to_block:,}\n"
        f"Total Supply Increase: {supply_delta:,.2f} USDai\n"
        f"Sum of Transfer-based mint events: {mint_events_total:,.2f} USDai\n"
        f"Unexplained increase: {unexplained:,.2f} USDai\n\n"
        "Potential non-standard mint path detected. Please investigate bridge/admin mint paths."
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
        to_block = latest_block - CONFIRMATIONS
        if to_block <= 0:
            logger.warning("Latest block is too low to scan safely (latest=%s).", latest_block)
            return

        last_block_cached = _to_int(get_last_value_for_key_from_file(cache_filename, CACHE_KEY_LAST_BLOCK))
        last_supply_cached = _to_int(get_last_value_for_key_from_file(cache_filename, CACHE_KEY_LAST_SUPPLY))

        if last_block_cached > 0:
            from_block = last_block_cached + 1
        else:
            from_block = max(0, to_block - INITIAL_LOOKBACK_BLOCKS + 1)
            logger.info(
                "No cached block found. Initializing scan window to last %s blocks (%s -> %s).",
                INITIAL_LOOKBACK_BLOCKS,
                from_block,
                to_block,
            )

        if from_block > to_block:
            logger.info("No new finalized blocks to scan. from_block=%s to_block=%s", from_block, to_block)
            write_last_value_to_file(cache_filename, CACHE_KEY_LAST_BLOCK, to_block)
            current_supply_raw = int(usdai.functions.totalSupply().call(block_identifier=to_block))
            write_last_value_to_file(cache_filename, CACHE_KEY_LAST_SUPPLY, current_supply_raw)
            return

        mint_logs = _fetch_mint_logs(client, from_block, to_block)
        logger.info("Fetched %s mint-like Transfer logs from block %s to %s", len(mint_logs), from_block, to_block)

        large_mints: list[dict] = []
        mint_events_total_raw = 0

        for log in mint_logs:
            amount_raw = int(log["data"].hex(), 16) if hasattr(log["data"], "hex") else int(str(log["data"]), 16)
            mint_events_total_raw += amount_raw
            if amount_raw >= threshold_raw:
                to_addr = _extract_topic_address(log["topics"][2])
                tx_hash = (
                    log["transactionHash"].hex()
                    if hasattr(log["transactionHash"], "hex")
                    else str(log["transactionHash"])
                )
                large_mints.append(
                    {
                        "amount_raw": amount_raw,
                        "to": to_addr,
                        "tx_hash": tx_hash,
                        "block_number": int(log["blockNumber"]),
                    }
                )

        if large_mints:
            _send_large_mints_alert(large_mints, decimals, from_block, to_block)

        current_supply_raw = int(usdai.functions.totalSupply().call(block_identifier=to_block))
        if last_supply_cached > 0:
            supply_delta_raw = current_supply_raw - last_supply_cached
            if supply_delta_raw >= threshold_raw and supply_delta_raw > mint_events_total_raw:
                _send_unexplained_supply_jump_alert(
                    supply_delta_raw=supply_delta_raw,
                    mint_events_total_raw=mint_events_total_raw,
                    decimals=decimals,
                    from_block=from_block,
                    to_block=to_block,
                )

        write_last_value_to_file(cache_filename, CACHE_KEY_LAST_BLOCK, to_block)
        write_last_value_to_file(cache_filename, CACHE_KEY_LAST_SUPPLY, current_supply_raw)

    except Exception as exc:
        logger.error("USDai large mint monitoring failed: %s", exc)
        send_alert(Alert(AlertSeverity.MEDIUM, f"USDai large mint monitor failed: {exc}", PROTOCOL), plain_text=True)


if __name__ == "__main__":
    main()
