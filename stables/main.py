"""Stablecoin depeg price monitoring — runs on a fast schedule (every 10-15 min).

Fetches all monitored stablecoin prices in a single DeFiLlama call and routes
depeg alerts to the owning protocol's Telegram channel.
"""

from utils.defillama import check_stablecoin_prices
from utils.logging import get_logger

logger = get_logger("stables")

# (display_name, defillama_key, protocol for telegram routing)
MONITORED_TOKENS: list[tuple[str, str, str]] = [
    # ethena
    ("USDe", "ethereum:0x4c9EDD5852cd905f086C759E8383e09bff1E68B3", "ethena"),
    ("sUSDe", "ethereum:0x9D39A5DE30e57443BfF2A8307A4256c8797A3497", "ethena"),
    # infinifi
    ("iUSD", "ethereum:0x48f9e38f3070AD8945DFEae3FA70987722E3D89c", "infinifi"),
    # maple
    ("syrupUSDC", "ethereum:0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b", "maple"),
    ("syrupUSDT", "ethereum:0x356b8d89c1e1239cbbb9de4815c39a1474d5ba7d", "maple"),
    # cap
    ("cUSD", "ethereum:0xcccc62962d17b8914c62d74ffb843d73b2a3cccc", "cap"),
]


def main() -> None:
    """Check all stablecoin prices, grouping alerts per protocol."""
    # Group tokens by protocol so each protocol gets its own alert
    by_protocol: dict[str, list[tuple[str, str]]] = {}
    for name, key, protocol in MONITORED_TOKENS:
        by_protocol.setdefault(protocol, []).append((name, key))

    for protocol, tokens in by_protocol.items():
        check_stablecoin_prices(tokens, protocol)

    logger.info("Stablecoin price check complete (%d tokens)", len(MONITORED_TOKENS))


if __name__ == "__main__":
    main()
