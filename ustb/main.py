"""USTB (Superstate Short Duration US Government Securities Fund) monitoring.

Monitors on Ethereum Mainnet:
1. NAV/Share — compares Continuous Price Oracle and Chainlink feed.
   Alerts on any NAV decrease (fund losses) or divergence > 0.5%.
2. RedemptionIdle — USDC balance held by the RedemptionIdle contract.
   Alerts when below $500K.
3. Large supply changes — alerts on >10% total supply change vs 24h-cached value.
4. Oracle staleness — alerts if latest checkpoint effectiveAt is > 4 days old
   (oracle reverts at 5 days).

Run hourly via GitHub Actions.
"""

from utils.abi import load_abi
from utils.alert import Alert, AlertSeverity, send_alert
from utils.cache import get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.formatting import format_usd
from utils.logging import get_logger
from utils.web3_wrapper import ChainManager

PROTOCOL = "ustb"
logger = get_logger(PROTOCOL)

# ---------------------------------------------------------------------------
# Contract addresses (Ethereum Mainnet)
# ---------------------------------------------------------------------------
USTB_TOKEN = "0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e"
CONTINUOUS_ORACLE = "0xE4fA682f94610cCd170680cc3B045d77D9E528a8"
CHAINLINK_ORACLE = "0x289B5036cd942e619E1Ee48670F98d214E745AAC"
REDEMPTION_IDLE = "0x4c21B7577C8FE8b0B0669165ee7C8f67fa1454Cf"
USDC_TOKEN = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
ORACLE_DIFF_THRESHOLD = 0.005  # 0.5%
REDEMPTION_MIN_USDC = 500_000  # $500K
SUPPLY_CHANGE_THRESHOLD = 0.10  # 10%
STALENESS_THRESHOLD = 345_600  # 4 days in seconds (revert at 5 days / 432_000s)

# ---------------------------------------------------------------------------
# Cache keys (shared cache-id.txt used by the hourly workflow)
# ---------------------------------------------------------------------------
CACHE_FILE = "cache-id.txt"
CACHE_KEY_SUPPLY = "ustb_total_supply"
CACHE_KEY_SUPPLY_TS = "ustb_supply_ts"
CACHE_KEY_CHAINLINK_NAV = "ustb_chainlink_nav"

# ---------------------------------------------------------------------------
# ABIs
# ---------------------------------------------------------------------------
ABI_ORACLE = load_abi("ustb/abi/SuperstateOracle.json")
ABI_CHAINLINK = load_abi("ustb/abi/ChainlinkAggregator.json")
ABI_ERC20 = load_abi("common-abi/ERC20.json")

USTB_DECIMALS = 6
USDC_DECIMALS = 6


def main() -> None:
    """Run all USTB monitoring checks."""
    client = ChainManager.get_client(Chain.MAINNET)

    oracle = client.eth.contract(address=CONTINUOUS_ORACLE, abi=ABI_ORACLE)
    chainlink = client.eth.contract(address=CHAINLINK_ORACLE, abi=ABI_CHAINLINK)
    usdc = client.eth.contract(address=USDC_TOKEN, abi=ABI_ERC20)
    ustb = client.eth.contract(address=USTB_TOKEN, abi=ABI_ERC20)

    # --- Batch 1: all independent reads ------------------------------------------------
    with client.batch_requests() as batch:
        batch.add(oracle.functions.latestRoundData())
        batch.add(oracle.functions.decimals())
        batch.add(chainlink.functions.latestRoundData())
        batch.add(chainlink.functions.decimals())
        batch.add(usdc.functions.balanceOf(REDEMPTION_IDLE))
        batch.add(ustb.functions.totalSupply())
        responses = client.execute_batch(batch)

    oracle_round_data = responses[0]
    oracle_decimals = int(responses[1])
    chainlink_round_data = responses[2]
    chainlink_decimals = int(responses[3])
    usdc_balance_raw = int(responses[4])
    total_supply_raw = int(responses[5])

    oracle_round_id = int(oracle_round_data[0])
    oracle_answer = int(oracle_round_data[1])
    chainlink_answer = int(chainlink_round_data[1])

    oracle_price = oracle_answer / (10**oracle_decimals)
    chainlink_price = chainlink_answer / (10**chainlink_decimals)

    # --- Batch 2: checkpoint data (needs roundId from batch 1) -------------------------
    with client.batch_requests() as batch:
        batch.add(oracle.functions.checkpoints(oracle_round_id))
        if oracle_round_id > 0:
            batch.add(oracle.functions.checkpoints(oracle_round_id - 1))
        checkpoint_responses = client.execute_batch(batch)

    current_timestamp = int(client.eth.get_block("latest")["timestamp"])

    latest_checkpoint = checkpoint_responses[0]
    effective_at = int(latest_checkpoint[1])

    _check_nav_monotonicity(oracle_round_id, checkpoint_responses, oracle_decimals)
    _check_chainlink_monotonicity(chainlink_answer, chainlink_decimals)
    _check_oracle_divergence(oracle_price, chainlink_price)
    _check_redemption_idle(usdc_balance_raw)
    _check_supply_change(total_supply_raw, current_timestamp, oracle_price)
    _check_oracle_staleness(current_timestamp, effective_at)

    logger.info(
        "USTB monitoring complete — NAV: $%.6f, supply: %s",
        oracle_price,
        format_usd(_to_tokens(total_supply_raw) * oracle_price),
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_nav_monotonicity(
    round_id: int,
    checkpoint_responses: list,
    oracle_decimals: int,
) -> None:
    """Alert if the latest NAV/Share checkpoint is lower than the previous one."""
    if round_id <= 0 or len(checkpoint_responses) < 2:
        logger.info("Not enough checkpoints to compare (roundId=%d)", round_id)
        return

    current_navs = int(checkpoint_responses[0][2])
    prev_navs = int(checkpoint_responses[1][2])

    if current_navs < prev_navs:
        decrease_pct = (prev_navs - current_navs) / prev_navs * 100
        send_alert(
            Alert(
                AlertSeverity.CRITICAL,
                f"USTB NAV/Share DECREASED\n"
                f"Previous: ${prev_navs / (10**oracle_decimals):.6f}\n"
                f"Current: ${current_navs / (10**oracle_decimals):.6f}\n"
                f"Decrease: {decrease_pct:.4f}%",
                PROTOCOL,
            )
        )
    else:
        logger.info(
            "NAV/Share checkpoint: $%.6f -> $%.6f (monotonic OK)",
            prev_navs / (10**oracle_decimals),
            current_navs / (10**oracle_decimals),
        )


def _check_oracle_divergence(oracle_price: float, chainlink_price: float) -> None:
    """Alert if the Continuous Oracle and Chainlink feed differ by more than 0.5%."""
    if chainlink_price <= 0:
        logger.warning("Chainlink price is zero, skipping divergence check")
        return

    diff = abs(oracle_price - chainlink_price) / chainlink_price
    logger.info(
        "Oracle prices — Continuous: $%.6f, Chainlink: $%.6f, diff: %.4f%%",
        oracle_price,
        chainlink_price,
        diff * 100,
    )
    if diff > ORACLE_DIFF_THRESHOLD:
        send_alert(
            Alert(
                AlertSeverity.HIGH,
                f"USTB oracle price divergence > {ORACLE_DIFF_THRESHOLD:.1%}\n"
                f"Continuous Oracle: ${oracle_price:.6f}\n"
                f"Chainlink: ${chainlink_price:.6f}\n"
                f"Difference: {diff:.4%}",
                PROTOCOL,
            )
        )


def _check_chainlink_monotonicity(chainlink_answer: int, chainlink_decimals: int) -> None:
    """Alert if the Chainlink NAV feed decreases versus the last observed value."""
    previous_answer = get_last_value_for_key_from_file(CACHE_FILE, CACHE_KEY_CHAINLINK_NAV)
    try:
        previous_answer_int = int(previous_answer)
    except (TypeError, ValueError):
        previous_answer_int = 0

    if previous_answer_int > 0 and chainlink_answer < previous_answer_int:
        previous_price = previous_answer_int / (10**chainlink_decimals)
        current_price = chainlink_answer / (10**chainlink_decimals)
        decrease_pct = (previous_answer_int - chainlink_answer) / previous_answer_int * 100
        send_alert(
            Alert(
                AlertSeverity.CRITICAL,
                f"USTB Chainlink NAV DECREASED\n"
                f"Previous: ${previous_price:.6f}\n"
                f"Current: ${current_price:.6f}\n"
                f"Decrease: {decrease_pct:.4f}%",
                PROTOCOL,
            )
        )

    if chainlink_answer != previous_answer_int:
        write_last_value_to_file(CACHE_FILE, CACHE_KEY_CHAINLINK_NAV, chainlink_answer)


def _check_redemption_idle(usdc_balance_raw: int) -> None:
    """Alert if RedemptionIdle USDC balance drops below threshold."""
    usdc_balance = usdc_balance_raw / (10**USDC_DECIMALS)
    logger.info("RedemptionIdle USDC balance: %s", format_usd(usdc_balance))
    if usdc_balance < REDEMPTION_MIN_USDC:
        send_alert(
            Alert(
                AlertSeverity.HIGH,
                f"USTB RedemptionIdle USDC below threshold\n"
                f"Balance: {format_usd(usdc_balance)}\n"
                f"Threshold: {format_usd(REDEMPTION_MIN_USDC)}\n"
                f"Contract: https://etherscan.io/address/{REDEMPTION_IDLE}",
                PROTOCOL,
            )
        )


def _check_supply_change(total_supply_raw: int, current_timestamp: int, nav_price: float) -> None:
    """Alert if total supply changed by more than 10% compared to the 24h-cached value.

    The cached supply value is only updated once every 24 hours so that hourly
    runs compare against the same baseline.
    """
    total_supply = _to_tokens(total_supply_raw)

    prev_supply_str = str(get_last_value_for_key_from_file(CACHE_FILE, CACHE_KEY_SUPPLY))
    prev_ts_str = str(get_last_value_for_key_from_file(CACHE_FILE, CACHE_KEY_SUPPLY_TS))

    if prev_supply_str == "0" or prev_ts_str == "0":
        logger.info("No cached supply found, initialising cache")
        write_last_value_to_file(CACHE_FILE, CACHE_KEY_SUPPLY, total_supply_raw)
        write_last_value_to_file(CACHE_FILE, CACHE_KEY_SUPPLY_TS, current_timestamp)
        return

    prev_supply_raw = int(prev_supply_str)
    prev_ts = int(prev_ts_str)
    prev_supply = _to_tokens(prev_supply_raw)

    if prev_supply > 0:
        supply_change = (total_supply - prev_supply) / prev_supply
        logger.info("Supply change vs cached: %+.2f%%", supply_change * 100)
        if abs(supply_change) > SUPPLY_CHANGE_THRESHOLD:
            send_alert(
                Alert(
                    AlertSeverity.HIGH,
                    f"USTB large supply change detected (>{SUPPLY_CHANGE_THRESHOLD:.0%} in 24h)\n"
                    f"Previous: {format_usd(prev_supply * nav_price)} ({prev_supply:,.2f} USTB)\n"
                    f"Current: {format_usd(total_supply * nav_price)} ({total_supply:,.2f} USTB)\n"
                    f"Change: {supply_change:+.2%}",
                    PROTOCOL,
                )
            )

    # Refresh baseline every 24 hours
    if current_timestamp - prev_ts >= 86_400:
        write_last_value_to_file(CACHE_FILE, CACHE_KEY_SUPPLY, total_supply_raw)
        write_last_value_to_file(CACHE_FILE, CACHE_KEY_SUPPLY_TS, current_timestamp)


def _check_oracle_staleness(current_timestamp: int, effective_at: int) -> None:
    """Alert if the latest oracle checkpoint is older than 4 days.

    The SuperstateOracle reverts at 5 days (432_000s); we alert at 4 days
    (345_600s) to provide a one-day buffer.
    """
    staleness = current_timestamp - effective_at
    staleness_days = staleness / 86_400
    logger.info("Oracle staleness: %.1f hours (%.1f days)", staleness / 3600, staleness_days)
    if staleness > STALENESS_THRESHOLD:
        send_alert(
            Alert(
                AlertSeverity.HIGH,
                f"USTB oracle stale — revert at 5 days\n"
                f"Staleness: {staleness_days:.1f} days\n"
                f"Threshold: 4 days (345,600s)\n"
                f"Last effectiveAt: {effective_at}",
                PROTOCOL,
            )
        )


def _to_tokens(raw: int) -> float:
    """Convert raw USTB amount to human-readable float."""
    return raw / 10**USTB_DECIMALS  # type: ignore[no-any-return]


if __name__ == "__main__":
    main()
