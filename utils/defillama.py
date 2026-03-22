"""DeFiLlama price utilities for stablecoin depeg monitoring."""

from decimal import Decimal, getcontext

from defillama_sdk import DefiLlama

from utils.logging import get_logger
from utils.telegram import send_telegram_message

getcontext().prec = 18

logger = get_logger("defillama")

DEPEG_THRESHOLD = Decimal("0.995")

_dl_client = DefiLlama()


def check_stablecoin_prices(
    tokens: list[tuple[str, str]],
    protocol: str,
    threshold: Decimal = DEPEG_THRESHOLD,
) -> None:
    """Fetch prices for stablecoins via DeFiLlama and alert on depeg.

    Args:
        tokens: List of (display_name, defillama_key) tuples.
            DeFiLlama key format: "chain:token_address".
        protocol: Protocol name for Telegram routing.
        threshold: Price below which a depeg alert is sent.
    """
    token_keys = [key for _, key in tokens]
    logger.info("Fetching prices for %d tokens from DeFiLlama", len(token_keys))
    result = _dl_client.prices.getCurrentPrices(token_keys)
    coins = result.get("coins", {})
    prices = {key: Decimal(str(data["price"])) for key, data in coins.items() if "price" in data}

    depegged: list[tuple[str, Decimal]] = []

    for name, key in tokens:
        price = prices.get(key)
        if price is None:
            logger.warning("No price returned for %s (%s)", name, key)
            continue
        logger.info("%s price: $%s", name, price)
        if price < threshold:
            depegged.append((name, price))

    if depegged:
        lines = [f"*{name}*: ${price}" for name, price in depegged]
        message = f"🚨 CRITICAL: Stablecoin Depeg (below ${threshold}):\n" + "\n".join(lines)
        send_telegram_message(message, protocol)
