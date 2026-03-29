"""DeFiLlama price utilities for stablecoin depeg monitoring."""

from decimal import Decimal, getcontext

from defillama_sdk import DefiLlama

from utils.alert import Alert, AlertSeverity, send_alert
from utils.logging import get_logger

getcontext().prec = 18

logger = get_logger("defillama")

DEPEG_THRESHOLD = Decimal("0.97")

_dl_client = DefiLlama()


def fetch_prices(token_keys: list[str]) -> dict[str, Decimal]:
    """Fetch current prices from DeFiLlama for the given token keys.

    Args:
        token_keys: List of DeFiLlama keys ("chain:token_address").

    Returns:
        Mapping of token key to price as Decimal. Missing tokens are omitted.

    Raises:
        Exception: If the DeFiLlama API call fails.
    """
    logger.info("Fetching prices for %d tokens from DeFiLlama", len(token_keys))
    result = _dl_client.prices.getCurrentPrices(token_keys)
    coins = result.get("coins", {})
    return {key: Decimal(str(data["price"])) for key, data in coins.items() if "price" in data}


def check_stablecoin_prices(
    tokens: list[tuple[str, str]],
    protocol: str,
    threshold: Decimal = DEPEG_THRESHOLD,
    prices: dict[str, Decimal] | None = None,
) -> None:
    """Check stablecoin prices and alert on depeg.

    Args:
        tokens: List of (display_name, defillama_key) tuples.
        protocol: Protocol name for Telegram routing.
        threshold: Price below which a depeg alert is sent.
        prices: Pre-fetched prices from ``fetch_prices``. If None, prices
            are fetched inline (one API call per invocation).
    """
    if prices is None:
        try:
            prices = fetch_prices([key for _, key in tokens])
        except Exception as exc:
            logger.warning("Failed to fetch DeFiLlama prices for %s: %s", protocol, exc)
            send_alert(Alert(AlertSeverity.LOW, f"Stablecoin price check failed: {exc}", protocol))
            return

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
        message = f"Stablecoin Depeg (below ${threshold}):\n" + "\n".join(lines)
        send_alert(Alert(AlertSeverity.CRITICAL, message, protocol))
