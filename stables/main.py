#!/usr/bin/env python3
"""Stablecoin price monitoring via DeFiLlama.

Fetches current prices for a set of stablecoins and sends a critical Telegram
alert when any token drops below the configured depeg threshold.
"""

from decimal import Decimal, getcontext

from defillama_sdk import DefiLlama

from utils.logging import get_logger
from utils.telegram import send_telegram_message

getcontext().prec = 18

PROTOCOL = "stables"
logger = get_logger(PROTOCOL)

DEPEG_THRESHOLD = Decimal("0.995")

# Tokens to monitor: (display_name, defillama_key)
# DeFiLlama key format: "chain:token_address"
STABLECOINS: list[tuple[str, str]] = [
    ("DAI", "ethereum:0x6b175474e89094c44da98b954eedeac495271d0f"),
    ("USDS", "ethereum:0xdC035D45d973E3EC169d2276DDab16f1e407384F"),
    ("USDe", "ethereum:0x4c9edd5852cd905f086c759e8383e09bff1e68b3"),
    ("sUSDe", "ethereum:0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"),
    ("syrupUSDC", "ethereum:0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b"),
    ("syrupUSDT", "ethereum:0x8a4f85BeC4fC7340907e6e86C7721DC3B0506A4C"),
    ("USDT", "ethereum:0xdAC17F958D2ee523a2206206994597C13D831ec7"),
    ("USDC", "ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
    ("FRAX", "ethereum:0x853d955aCEf822Db058eb8505911ED77F175b99e"),
    ("crvUSD", "ethereum:0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E"),
    ("GHO", "ethereum:0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f"),
    ("PYUSD", "ethereum:0x6c3ea9036406852006290770BEdFcAbA0e23A0e8"),
    ("USD0", "ethereum:0x73A15FeD60Bf67631dC6cd7Bc5B6e8da8190aCF5"),
]

_dl_client = DefiLlama()


def _fetch_prices(token_keys: list[str]) -> dict[str, Decimal]:
    """Fetch current prices for multiple tokens from DeFiLlama in a single call.

    Args:
        token_keys: List of tokens in "chain:address" format.

    Returns:
        Mapping of token key to price as Decimal.
    """
    logger.info("Fetching prices for %d tokens from DeFiLlama", len(token_keys))
    result = _dl_client.prices.getCurrentPrices(token_keys)
    coins = result.get("coins", {})
    return {key: Decimal(str(data["price"])) for key, data in coins.items() if "price" in data}


def check_stablecoin_prices() -> None:
    """Check all stablecoin prices and alert on depegs."""
    token_keys = [key for _, key in STABLECOINS]
    prices = _fetch_prices(token_keys)

    depegged: list[tuple[str, Decimal]] = []

    for name, key in STABLECOINS:
        price = prices.get(key)
        if price is None:
            logger.warning("No price returned for %s (%s)", name, key)
            continue

        logger.info("%s price: $%s", name, price)

        if price < DEPEG_THRESHOLD:
            depegged.append((name, price))

    if depegged:
        lines = [f"*{name}*: ${price}" for name, price in depegged]
        message = f"🚨 Stablecoin Depeg Alert (below ${DEPEG_THRESHOLD}):\n" + "\n".join(lines)
        send_telegram_message(message, PROTOCOL)
        logger.warning("Depeg alert sent for: %s", ", ".join(name for name, _ in depegged))
    else:
        logger.info("All stablecoins within peg (>= $%s)", DEPEG_THRESHOLD)


def main() -> None:
    """Entry point for stablecoin price monitoring."""
    logger.info("Starting stablecoin price check...")
    try:
        check_stablecoin_prices()
    except Exception as e:
        logger.error("Error checking stablecoin prices: %s", e)
        send_telegram_message(f"⚠️ Stablecoin price monitor error: {e}", PROTOCOL)
        raise


if __name__ == "__main__":
    main()
