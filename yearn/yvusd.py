"""
yvUSD vault monitoring script.

Monitors:
- APY anomalies: unlocked APY > locked APY inversion, negative strategy APR
- CCTP bridging delays: stale cross-chain strategy reports
- Flashloan liquidity: available liquidity for looper strategy unwinding
- Large cooldown requests: significant LockedyvUSD cooldown events
"""

import time

from utils.abi import load_abi
from utils.alert import Alert, AlertSeverity, send_alert
from utils.cache import get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.formatting import format_usd
from utils.http import fetch_json
from utils.logging import get_logger
from utils.web3_wrapper import ChainManager, Web3Client

PROTOCOL = "yvusd"
logger = get_logger(PROTOCOL)

CACHE_FILENAME = "cache-id.txt"

# --- ABIs ---
ABI_VAULT = load_abi("yearn/abi/YearnV3Vault.json")
ABI_MORPHO = load_abi("yearn/abi/Morpho.json")
ABI_LOCKED = load_abi("yearn/abi/LockedYvUSD.json")

# --- Contract Addresses ---
YVUSD_VAULT = "0x696d02Db93291651ED510704c9b286841d506987"
LOCKED_YVUSD = "0xAaaFEa48472f77563961Cdb53291DEDfB46F9040"
MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
BALANCER_VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"

# --- API ---
YVUSD_API_URL = "https://yvusd-api.yearn.fi/api/aprs"

# --- Thresholds ---
APY_INVERSION_HOURS = 6  # Alert after this many hours of unlocked APY > locked APY
STRATEGY_STALENESS_HOURS = 48  # Cross-chain strategy report staleness threshold
LARGE_COOLDOWN_THRESHOLD = 100_000  # $100K in USD

USDC_DECIMALS = 6
ONE_USDC = 10**USDC_DECIMALS

# --- Cache Keys ---
CACHE_KEY_APY_INVERSION_START = "YVUSD_APY_INVERSION_START"
CACHE_KEY_APY_INVERSION_ALERTED = "YVUSD_APY_INVERSION_ALERTED"
CACHE_KEY_LAST_BLOCK = "YVUSD_LAST_BLOCK"

# Number of blocks to scan per run (~1 hour at 12s/block)
BLOCKS_PER_HOUR = 300
MAX_SCAN_BLOCKS = 5000

# Minimal ERC20 ABI for balanceOf
ABI_ERC20_BALANCE = [
    {
        "type": "function",
        "name": "balanceOf",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    }
]

# Strategy types that use Morpho leverage and need flashloans to unwind
LOOPER_STRATEGY_TYPES = ("morpho-looper", "pt-morpho-looper")


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


def check_apy_anomalies(api_data: dict) -> None:
    """Check for APY anomalies using the yvUSD API.

    Alerts when:
    - Unlocked APY > locked APY for more than APY_INVERSION_HOURS
    - Any active strategy has negative APR
    """
    yvusd_data = api_data.get(YVUSD_VAULT)
    locked_data = api_data.get(LOCKED_YVUSD)

    if not yvusd_data or not locked_data:
        logger.error("Missing vault data in API response")
        send_alert(Alert(AlertSeverity.MEDIUM, "Missing vault data in yvUSD API response", PROTOCOL))
        return

    unlocked_apy = yvusd_data.get("apy", 0)
    locked_apy = locked_data.get("apy", 0)
    logger.info("APY — Unlocked: %.2f%%, Locked: %.2f%%", unlocked_apy * 100, locked_apy * 100)

    _check_apy_inversion(unlocked_apy, locked_apy)
    _check_negative_strategy_apr(yvusd_data)


def _check_apy_inversion(unlocked_apy: float, locked_apy: float) -> None:
    """Alert if unlocked APY exceeds locked APY for more than APY_INVERSION_HOURS."""
    now = time.time()

    if unlocked_apy > locked_apy:
        inversion_start = get_cache_value(CACHE_KEY_APY_INVERSION_START)
        if inversion_start == 0:
            set_cache_value(CACHE_KEY_APY_INVERSION_START, now)
            logger.warning(
                "APY inversion detected: unlocked (%.2f%%) > locked (%.2f%%)",
                unlocked_apy * 100,
                locked_apy * 100,
            )
        else:
            hours_inverted = (now - inversion_start) / 3600
            already_alerted = get_cache_value(CACHE_KEY_APY_INVERSION_ALERTED)
            if hours_inverted >= APY_INVERSION_HOURS and not already_alerted:
                message = (
                    f"*yvUSD APY Inversion Alert*\n"
                    f"Unlocked APY ({unlocked_apy:.2%}) > Locked APY ({locked_apy:.2%})\n"
                    f"Inverted for {hours_inverted:.1f} hours\n"
                    f"Locked users are earning less than unlocked — incentive misalignment\n"
                    f"[yvUSD Vault](https://etherscan.io/address/{YVUSD_VAULT})"
                )
                send_alert(Alert(AlertSeverity.HIGH, message, PROTOCOL))
                set_cache_value(CACHE_KEY_APY_INVERSION_ALERTED, 1)
    else:
        # Inversion resolved — reset tracking
        if get_cache_value(CACHE_KEY_APY_INVERSION_START) > 0:
            set_cache_value(CACHE_KEY_APY_INVERSION_START, 0)
            set_cache_value(CACHE_KEY_APY_INVERSION_ALERTED, 0)
            logger.info("APY inversion resolved")


def _check_negative_strategy_apr(yvusd_data: dict) -> None:
    """Alert if any active strategy has a negative APR."""
    strategies = yvusd_data.get("meta", {}).get("strategies", [])

    for strategy in strategies:
        apr_raw = int(strategy.get("apr_raw", "0"))
        debt = int(strategy.get("debt", "0"))
        name = strategy.get("meta", {}).get("name", strategy.get("address", "unknown"))
        address = strategy.get("address", "unknown")

        if debt > 0 and apr_raw < 0:
            apr_pct = apr_raw / 1e18 * 100
            debt_usd = debt / ONE_USDC
            message = (
                f"*yvUSD Negative Strategy APR*\n"
                f"{name}: {apr_pct:.2f}% APR\n"
                f"Debt: {format_usd(debt_usd)}\n"
                f"Strategy is losing money\n"
                f"[Strategy](https://etherscan.io/address/{address})"
            )
            send_alert(Alert(AlertSeverity.HIGH, message, PROTOCOL))


def check_strategy_staleness(client: Web3Client, api_data: dict) -> None:
    """Check cross-chain strategy report freshness.

    Alerts when a CCTP cross-chain strategy hasn't reported
    in more than STRATEGY_STALENESS_HOURS.
    """
    strategies = api_data.get(YVUSD_VAULT, {}).get("meta", {}).get("strategies", [])
    cross_chain = [s for s in strategies if s.get("meta", {}).get("type") == "cross-chain"]

    if not cross_chain:
        logger.info("No cross-chain strategies found")
        return

    vault = client.eth.contract(address=YVUSD_VAULT, abi=ABI_VAULT)

    with client.batch_requests() as batch:
        for strategy in cross_chain:
            batch.add(vault.functions.strategies(strategy["address"]))
        responses = client.execute_batch(batch)

    if len(responses) != len(cross_chain):
        logger.error("Unexpected batch response count for strategy staleness check")
        return

    now = int(time.time())

    for i, strategy in enumerate(cross_chain):
        activation, last_report, current_debt, max_debt = responses[i]
        name = strategy.get("meta", {}).get("name", strategy["address"])
        address = strategy["address"]

        if activation == 0:
            continue

        hours_since_report = (now - last_report) / 3600
        debt_usd = current_debt / ONE_USDC

        logger.info(
            "CCTP strategy %s — last report: %.1f hours ago, debt: %s",
            name,
            hours_since_report,
            format_usd(debt_usd),
        )

        if current_debt > 0 and hours_since_report > STRATEGY_STALENESS_HOURS:
            message = (
                f"*yvUSD CCTP Strategy Stale Report*\n"
                f"{name}\n"
                f"Last report: {hours_since_report:.1f} hours ago (threshold: {STRATEGY_STALENESS_HOURS}h)\n"
                f"Debt: {format_usd(debt_usd)}\n"
                f"Cross-chain accounting may be outdated\n"
                f"[Strategy](https://etherscan.io/address/{address})"
            )
            send_alert(Alert(AlertSeverity.HIGH, message, PROTOCOL))


def check_flashloan_liquidity(client: Web3Client, api_data: dict) -> None:
    """Check available flashloan liquidity for looper strategy unwinding.

    Compares each looper strategy's Morpho borrow position against available
    flashloan liquidity from the Balancer vault and Morpho market.
    """
    strategies = api_data.get(YVUSD_VAULT, {}).get("meta", {}).get("strategies", [])
    loopers = [
        s
        for s in strategies
        if s.get("meta", {}).get("type") in LOOPER_STRATEGY_TYPES
        and s.get("meta", {}).get("market_id")
        and int(s.get("debt", "0")) > 0
    ]

    if not loopers:
        logger.info("No active Morpho looper strategies found")
        return

    morpho = client.eth.contract(address=MORPHO, abi=ABI_MORPHO)
    usdc = client.eth.contract(address=USDC, abi=ABI_ERC20_BALANCE)

    with client.batch_requests() as batch:
        for strategy in loopers:
            market_id = bytes.fromhex(strategy["meta"]["market_id"][2:])
            batch.add(morpho.functions.market(market_id))
            batch.add(morpho.functions.position(market_id, strategy["address"]))
        batch.add(usdc.functions.balanceOf(BALANCER_VAULT))
        responses = client.execute_batch(batch)

    expected = len(loopers) * 2 + 1
    if len(responses) != expected:
        logger.error("Unexpected batch response count for flashloan liquidity check")
        return

    balancer_usdc = responses[-1] / ONE_USDC
    logger.info("Balancer vault USDC balance: %s", format_usd(balancer_usdc))

    for i, strategy in enumerate(loopers):
        market_data = responses[i * 2]
        position_data = responses[i * 2 + 1]

        total_supply_assets = market_data[0]
        total_borrow_assets = market_data[2]
        total_borrow_shares = market_data[3]
        borrow_shares = position_data[1]

        # Convert borrow shares to assets
        if total_borrow_shares > 0 and borrow_shares > 0:
            borrow_assets = borrow_shares * total_borrow_assets // total_borrow_shares
        else:
            borrow_assets = 0

        borrow_usd = borrow_assets / ONE_USDC
        market_liquidity = (total_supply_assets - total_borrow_assets) / ONE_USDC
        name = strategy.get("meta", {}).get("name", strategy["address"])
        address = strategy["address"]

        logger.info(
            "Looper %s — borrow: %s, market liquidity: %s",
            name,
            format_usd(borrow_usd),
            format_usd(market_liquidity),
        )

        if borrow_assets == 0:
            continue

        # Strategy needs to flashloan approximately borrow_assets to unwind.
        # Alert if neither Balancer vault nor Morpho market has sufficient liquidity.
        if balancer_usdc < borrow_usd and market_liquidity < borrow_usd:
            message = (
                f"*yvUSD Flashloan Liquidity Warning*\n"
                f"{name}\n"
                f"Borrow position: {format_usd(borrow_usd)}\n"
                f"Balancer flashloan available: {format_usd(balancer_usdc)}\n"
                f"Morpho market liquidity: {format_usd(market_liquidity)}\n"
                f"Insufficient flashloan liquidity for strategy unwinding\n"
                f"[Strategy](https://etherscan.io/address/{address})"
            )
            send_alert(Alert(AlertSeverity.HIGH, message, PROTOCOL))


def check_large_cooldowns(client: Web3Client) -> None:
    """Check for large cooldown requests on LockedyvUSD.

    Scans recent blocks for CooldownStarted events exceeding LARGE_COOLDOWN_THRESHOLD.
    """
    locked = client.eth.contract(address=LOCKED_YVUSD, abi=ABI_LOCKED)

    current_block = client.eth.block_number
    last_block = int(get_cache_value(CACHE_KEY_LAST_BLOCK))

    if last_block == 0:
        from_block = current_block - BLOCKS_PER_HOUR
    else:
        from_block = last_block + 1

    if from_block >= current_block:
        logger.info("No new blocks to scan for cooldown events")
        set_cache_value(CACHE_KEY_LAST_BLOCK, current_block)
        return

    # Cap scan range to avoid hitting RPC limits
    if current_block - from_block > MAX_SCAN_BLOCKS:
        from_block = current_block - MAX_SCAN_BLOCKS
        logger.warning("Capped scan range to last %d blocks", MAX_SCAN_BLOCKS)

    logger.info("Scanning blocks %d to %d for cooldown events", from_block, current_block)

    try:
        events = locked.events.CooldownStarted.get_logs(fromBlock=from_block, toBlock=current_block)
    except Exception as e:
        logger.warning("Could not fetch CooldownStarted events: %s", e)
        set_cache_value(CACHE_KEY_LAST_BLOCK, current_block)
        return

    large_count = 0
    for event in events:
        shares = event["args"]["shares"]
        owner = event["args"]["user"]
        # yvUSD shares are roughly 1:1 with USDC (PPS ~ 1.004)
        shares_usd = shares / ONE_USDC

        if shares_usd >= LARGE_COOLDOWN_THRESHOLD:
            large_count += 1
            message = (
                f"*yvUSD Large Cooldown Request*\n"
                f"{format_usd(shares_usd)} cooldown requested\n"
                f"Owner: [{owner}](https://etherscan.io/address/{owner})\n"
                f"Cooldown period: 14 days\n"
                f"Large withdrawal incoming — may impact vault liquidity\n"
                f"[LockedyvUSD](https://etherscan.io/address/{LOCKED_YVUSD})"
            )
            send_alert(Alert(AlertSeverity.HIGH, message, PROTOCOL))

    logger.info("Found %d cooldown events (%d large)", len(events), large_count)
    set_cache_value(CACHE_KEY_LAST_BLOCK, current_block)


def main() -> None:
    """Run all yvUSD monitoring checks."""
    logger.info("Starting yvUSD monitoring...")

    client = ChainManager.get_client(Chain.MAINNET)

    try:
        api_data = fetch_json(YVUSD_API_URL)
        if api_data:
            check_apy_anomalies(api_data)
            check_strategy_staleness(client, api_data)
            check_flashloan_liquidity(client, api_data)
        else:
            send_alert(Alert(AlertSeverity.MEDIUM, "Failed to fetch yvUSD API data", PROTOCOL))
    except Exception as e:
        logger.error("Error during yvUSD API checks: %s", e)
        send_alert(Alert(AlertSeverity.MEDIUM, f"yvUSD API checks failed: {e}", PROTOCOL))

    try:
        check_large_cooldowns(client)
    except Exception as e:
        logger.error("Error during cooldown check: %s", e)
        send_alert(Alert(AlertSeverity.MEDIUM, f"yvUSD cooldown check failed: {e}", PROTOCOL))

    logger.info("yvUSD monitoring complete")


if __name__ == "__main__":
    main()
