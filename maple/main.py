"""
Maple Finance syrupUSDC monitoring script.

Monitors:
- PPS (Price Per Share) via convertToAssets(1e6) — alerts on any decrease
- TVL (Total Value Locked) via totalAssets() — alerts on >5% change in 24h
- Unrealized losses on loan managers — alerts on any non-zero value
- Strategy allocations (Aave and Sky) — tracks DeFi allocation changes
"""

from utils.abi import load_abi
from utils.cache import get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.formatting import format_usd
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "maple"
logger = get_logger(PROTOCOL)

CACHE_FILENAME = "cache-id.txt"

# --- ABIs ---
ABI_POOL = load_abi("maple/abi/SyrupUSDCPool.json")
ABI_LOAN_MANAGER = load_abi("maple/abi/LoanManager.json")
ABI_STRATEGY = load_abi("maple/abi/Strategy.json")

# --- Contract Addresses ---
SYRUP_USDC_POOL = "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"
FIXED_TERM_LOAN_MANAGER = "0x4A1c3F0D9aD0b3f9dA085bEBfc22dEA54263371b"
OPEN_TERM_LOAN_MANAGER = "0x6ACEb4cAbA81Fa6a8065059f3A944fb066A10fAc"
AAVE_STRATEGY = "0x560B3A85Af1cEF113BB60105d0Cf21e1d05F91d4"
SKY_STRATEGY = "0x859C9980931fa0A63765fD8EF2e29918Af5b038C"

# USDC has 6 decimals
USDC_DECIMALS = 6
ONE_SHARE = 10**USDC_DECIMALS  # 1e6

# --- Cache Keys ---
CACHE_KEY_PPS = "MAPLE_PPS"
CACHE_KEY_TVL = "MAPLE_TVL"

# --- Thresholds ---
TVL_CHANGE_THRESHOLD = 0.05  # 5% TVL change alert


def get_cache_value(key: str) -> float:
    """Read a cached float value, returns 0 if not found."""
    val = get_last_value_for_key_from_file(CACHE_FILENAME, key)
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def set_cache_value(key: str, value: float) -> None:
    """Write a float value to cache."""
    write_last_value_to_file(CACHE_FILENAME, key, value)


def check_pps(client, pool) -> float:
    """Check Price Per Share and alert on decrease."""
    pps = client.execute(pool.functions.convertToAssets(ONE_SHARE).call)
    pps_float = pps / ONE_SHARE

    previous_pps = get_cache_value(CACHE_KEY_PPS)
    logger.info("syrupUSDC PPS: %.8f (previous: %.8f)", pps_float, previous_pps)

    if previous_pps > 0 and pps_float < previous_pps:
        decrease_pct = (previous_pps - pps_float) / previous_pps * 100
        message = (
            f"🚨 *Maple syrupUSDC PPS Decrease*\n"
            f"📉 PPS dropped from {previous_pps:.8f} to {pps_float:.8f}\n"
            f"📊 Decrease: {decrease_pct:.4f}%\n"
            f"⚠️ This may indicate loan impairment or loss\n"
            f"🔗 [syrupUSDC Pool](https://etherscan.io/address/{SYRUP_USDC_POOL})"
        )
        send_telegram_message(message, PROTOCOL)

    if pps_float != previous_pps:
        set_cache_value(CACHE_KEY_PPS, pps_float)
    return pps_float


def check_tvl(client, pool) -> float:
    """Check Total Value Locked and alert on large changes."""
    total_assets = client.execute(pool.functions.totalAssets().call)
    tvl_usd = total_assets / ONE_SHARE

    previous_tvl = get_cache_value(CACHE_KEY_TVL)
    logger.info("syrupUSDC TVL: %s (previous: %s)", format_usd(tvl_usd), format_usd(previous_tvl))

    if previous_tvl > 0:
        change_pct = abs(tvl_usd - previous_tvl) / previous_tvl
        if change_pct >= TVL_CHANGE_THRESHOLD:
            direction = "increased" if tvl_usd > previous_tvl else "decreased"
            message = (
                f"🚨 *Maple syrupUSDC TVL Change*\n"
                f"💰 TVL {direction} by {change_pct:.2%}\n"
                f"📊 {format_usd(previous_tvl)} → {format_usd(tvl_usd)}\n"
                f"🔗 [syrupUSDC Pool](https://etherscan.io/address/{SYRUP_USDC_POOL})"
            )
            send_telegram_message(message, PROTOCOL)

    if tvl_usd != previous_tvl:
        set_cache_value(CACHE_KEY_TVL, tvl_usd)
    return tvl_usd


def check_unrealized_losses(client) -> None:
    """Check unrealized losses on both loan managers."""
    fixed_lm = client.eth.contract(address=FIXED_TERM_LOAN_MANAGER, abi=ABI_LOAN_MANAGER)
    open_lm = client.eth.contract(address=OPEN_TERM_LOAN_MANAGER, abi=ABI_LOAN_MANAGER)

    with client.batch_requests() as batch:
        batch.add(fixed_lm.functions.unrealizedLosses())
        batch.add(open_lm.functions.unrealizedLosses())
        batch.add(fixed_lm.functions.assetsUnderManagement())
        batch.add(open_lm.functions.assetsUnderManagement())

        responses = client.execute_batch(batch)
        if len(responses) != 4:
            raise ValueError(f"Expected 4 responses, got {len(responses)}")

    fixed_losses = responses[0] / ONE_SHARE
    open_losses = responses[1] / ONE_SHARE
    fixed_aum = responses[2] / ONE_SHARE
    open_aum = responses[3] / ONE_SHARE

    logger.info(
        "Loan managers — Fixed: AUM=%s, Losses=%s | Open: AUM=%s, Losses=%s",
        format_usd(fixed_aum),
        format_usd(fixed_losses),
        format_usd(open_aum),
        format_usd(open_losses),
    )

    total_losses = fixed_losses + open_losses
    if total_losses > 0:
        message = (
            f"🚨 *Maple syrupUSDC Unrealized Losses Detected*\n"
            f"📊 Fixed Term: {format_usd(fixed_losses)} (AUM: {format_usd(fixed_aum)})\n"
            f"📊 Open Term: {format_usd(open_losses)} (AUM: {format_usd(open_aum)})\n"
            f"⚠️ Loan impairment may be in progress\n"
            f"🔗 [FixedTermLM](https://etherscan.io/address/{FIXED_TERM_LOAN_MANAGER})\n"
            f"🔗 [OpenTermLM](https://etherscan.io/address/{OPEN_TERM_LOAN_MANAGER})"
        )
        send_telegram_message(message, PROTOCOL)



def check_strategy_allocations(client) -> None:
    """Check Aave and Sky strategy allocations."""
    aave_strategy = client.eth.contract(address=AAVE_STRATEGY, abi=ABI_STRATEGY)
    sky_strategy = client.eth.contract(address=SKY_STRATEGY, abi=ABI_STRATEGY)

    with client.batch_requests() as batch:
        batch.add(aave_strategy.functions.assetsUnderManagement())
        batch.add(sky_strategy.functions.assetsUnderManagement())

        responses = client.execute_batch(batch)
        if len(responses) != 2:
            raise ValueError(f"Expected 2 responses, got {len(responses)}")

    aave_assets = responses[0] / ONE_SHARE
    sky_assets = responses[1] / ONE_SHARE

    logger.info(
        "Strategy allocations — Aave: %s, Sky: %s",
        format_usd(aave_assets),
        format_usd(sky_assets),
    )


def main() -> None:
    logger.info("Starting Maple syrupUSDC monitoring...")

    client = ChainManager.get_client(Chain.MAINNET)
    pool = client.eth.contract(address=SYRUP_USDC_POOL, abi=ABI_POOL)

    try:
        pps = check_pps(client, pool)
        tvl = check_tvl(client, pool)
        check_unrealized_losses(client)
        check_strategy_allocations(client)

        logger.info(
            "Monitoring complete — PPS: %.8f, TVL: %s",
            pps,
            format_usd(tvl),
        )
    except Exception as e:
        logger.error("Error during Maple monitoring: %s", e)
        send_telegram_message(
            f"🚨 *Maple Monitoring Error*\n❌ {e}",
            PROTOCOL,
            plain_text=True,
        )


if __name__ == "__main__":
    main()
