"""Depeg monitoring for LRTs and stablecoins.

Uses Redstone fundamental oracles where available, falls back to DefiLlama pricing.
- Fundamental oracles: any depeg triggers CRITICAL alert
- DefiLlama pricing: 2%+ depeg triggers CRITICAL alert

LRT alerts are sent to a single "lrt" protocol channel, each identified by token symbol.
Stablecoin alerts are sent to a "stables" protocol channel.
"""

from dataclasses import dataclass
from decimal import Decimal, getcontext

from defillama_sdk import DefiLlama

from utils.abi import load_abi
from utils.alert import Alert, AlertSeverity, send_alert
from utils.chains import Chain
from utils.logging import get_logger
from utils.web3_wrapper import ChainManager

getcontext().prec = 18

logger = get_logger("prices")

LRT_PROTOCOL = "lrt"
STABLES_PROTOCOL = "stables"

# Oracle threshold: any meaningful depeg from fundamental oracle is critical
ORACLE_DEPEG_THRESHOLD = Decimal("0.998")
# DefiLlama threshold: 2% depeg from market price is critical
DEFILLAMA_DEPEG_THRESHOLD = Decimal("0.98")

# Reference tokens for LRT/BTC ratio computation via DefiLlama
WETH_KEY = "ethereum:0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

AGGREGATOR_V3_ABI = load_abi("prices/abi/AggregatorV3.json")

_dl_client = DefiLlama()


@dataclass(frozen=True)
class OracleAsset:
    """Asset monitored via on-chain Redstone fundamental oracle (AggregatorV3Interface)."""

    symbol: str
    oracle_address: str
    chain: Chain
    decimals: int
    protocol: str


@dataclass(frozen=True)
class DefiLlamaAsset:
    """Asset monitored via DefiLlama market price."""

    symbol: str
    defillama_key: str
    underlying: str  # "ETH" or "USD"
    protocol: str


# ---------------------------------------------------------------------------
# Oracle-monitored assets (Redstone fundamental push oracles)
# These implement AggregatorV3Interface with latestRoundData()
# ---------------------------------------------------------------------------
ORACLE_ASSETS: list[OracleAsset] = [
    # LBTC/BTC fundamental - Redstone push, 24h heartbeat / 1% deviation
    # Tenderly alert: eca272ef-979a-47b3-a7f0-2e67172889bb
    OracleAsset(
        symbol="LBTC",
        oracle_address="0xb415eAA355D8440ac7eCB602D3fb67ccC1f0bc81",
        chain=Chain.MAINNET,
        decimals=8,
        protocol=LRT_PROTOCOL,
    ),
    # cUSD/USD fundamental - Redstone push
    # Tenderly alert: 316f440e-457b-4cfa-a69e-f7f54230bf44
    OracleAsset(
        symbol="cUSD",
        oracle_address="0x9a5a3c3ed0361505cc1d4e824b3854de5724434a",
        chain=Chain.MAINNET,
        decimals=8,
        protocol=STABLES_PROTOCOL,
    ),
]

# ---------------------------------------------------------------------------
# DefiLlama-monitored LRT assets (market price vs ETH)
# No on-chain fundamental push oracle available on Ethereum mainnet.
# Redstone provides off-chain fundamental feeds for weETH, ezETH, rsETH,
# pufETH but these are pull-model (not persistent on-chain contracts).
# ---------------------------------------------------------------------------
DEFILLAMA_LRTS: list[DefiLlamaAsset] = [
    DefiLlamaAsset("weETH", "ethereum:0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("ezETH", "ethereum:0xbf5495Efe5DB9ce00f80364C8B423567e58d2110", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("rsETH", "ethereum:0xA1290d69c65A6Fe4DF752f95823Fae25cB99e5A7", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("pufETH", "ethereum:0xD9A442856C234a39a81a089C06451EBAa4306a72", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("osETH", "ethereum:0xf1C9acDc66974dFB6dEcB12aA385b9cD01190E38", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("rswETH", "ethereum:0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0", "ETH", LRT_PROTOCOL),
    DefiLlamaAsset("mETH", "ethereum:0xd5F7838F5C461fefF7FE49ea5ebaF7728bB0ADfa", "ETH", LRT_PROTOCOL),
]

# ---------------------------------------------------------------------------
# DefiLlama-monitored stablecoins (market price vs $1 USD)
# Blue-chip stables (USDC, USDT, DAI) are excluded; they are Tier 1 and
# extremely unlikely to depeg. Focus on higher-risk stables.
# ---------------------------------------------------------------------------
DEFILLAMA_STABLES: list[DefiLlamaAsset] = [
    DefiLlamaAsset("FDUSD", "ethereum:0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409", "USD", STABLES_PROTOCOL),
    DefiLlamaAsset("deUSD", "ethereum:0x15700B564Ca08D9439C58cA5053166E8317aa138", "USD", STABLES_PROTOCOL),
    DefiLlamaAsset("USD0", "ethereum:0x73A15FeD60Bf67631dC6cd7Bc5B6e8da8190aCF5", "USD", STABLES_PROTOCOL),
    DefiLlamaAsset("USD0++", "ethereum:0x35D8949372D46B7a3D5A56006AE77B215fc69bC0", "USD", STABLES_PROTOCOL),
    DefiLlamaAsset("USDe", "ethereum:0x4c9EDD5852cd905f086C759E8383e09bff1E68B3", "USD", STABLES_PROTOCOL),
]


def check_oracle_assets() -> None:
    """Check assets with on-chain fundamental oracles. Any depeg is CRITICAL."""
    # Group assets by chain for batch requests
    mainnet_assets = [a for a in ORACLE_ASSETS if a.chain == Chain.MAINNET]
    if not mainnet_assets:
        return

    client = ChainManager.get_client(Chain.MAINNET)

    with client.batch_requests() as batch:
        for asset in mainnet_assets:
            contract = client.eth.contract(
                address=client.w3.to_checksum_address(asset.oracle_address),
                abi=AGGREGATOR_V3_ABI,
            )
            batch.add(contract.functions.latestRoundData())
        responses = client.execute_batch(batch)

    if len(responses) != len(mainnet_assets):
        logger.error("Expected %d oracle responses, got %d", len(mainnet_assets), len(responses))
        return

    depegged_lrt: list[tuple[str, Decimal]] = []
    depegged_stables: list[tuple[str, Decimal]] = []

    for asset, result in zip(mainnet_assets, responses):
        try:
            # latestRoundData returns (roundId, answer, startedAt, updatedAt, answeredInRound)
            answer = Decimal(str(result[1])) / Decimal(10**asset.decimals)
            logger.info("%s oracle price: %s (threshold: %s)", asset.symbol, answer, ORACLE_DEPEG_THRESHOLD)

            if answer < ORACLE_DEPEG_THRESHOLD:
                if asset.protocol == LRT_PROTOCOL:
                    depegged_lrt.append((asset.symbol, answer))
                else:
                    depegged_stables.append((asset.symbol, answer))
        except Exception as exc:
            logger.error("Failed to parse oracle response for %s: %s", asset.symbol, exc)
            send_alert(Alert(AlertSeverity.MEDIUM, f"Oracle parse failed for {asset.symbol}: {exc}", asset.protocol))

    _send_depeg_alerts(depegged_lrt, LRT_PROTOCOL, "Oracle", ORACLE_DEPEG_THRESHOLD)
    _send_depeg_alerts(depegged_stables, STABLES_PROTOCOL, "Oracle", ORACLE_DEPEG_THRESHOLD)


def check_defillama_assets() -> None:
    """Check assets via DefiLlama market prices. 2%+ depeg is CRITICAL."""
    all_assets = DEFILLAMA_LRTS + DEFILLAMA_STABLES
    token_keys = list({a.defillama_key for a in all_assets} | {WETH_KEY})

    logger.info("Fetching prices for %d tokens from DefiLlama", len(token_keys))
    try:
        result = _dl_client.prices.getCurrentPrices(token_keys)
    except Exception as exc:
        logger.warning("Failed to fetch DefiLlama prices: %s", exc)
        send_alert(Alert(AlertSeverity.LOW, f"Depeg price fetch failed: {exc}", LRT_PROTOCOL))
        return

    coins = result.get("coins", {})
    prices = {key: Decimal(str(data["price"])) for key, data in coins.items() if "price" in data}

    eth_price = prices.get(WETH_KEY)
    if not eth_price:
        logger.error("Missing ETH reference price from DefiLlama")
        send_alert(Alert(AlertSeverity.MEDIUM, "Missing ETH reference price from DefiLlama", LRT_PROTOCOL))
        return

    depegged_lrt: list[tuple[str, Decimal]] = []
    depegged_stables: list[tuple[str, Decimal]] = []

    for asset in all_assets:
        price = prices.get(asset.defillama_key)
        if price is None:
            logger.warning("No price returned for %s (%s)", asset.symbol, asset.defillama_key)
            continue

        if asset.underlying == "ETH":
            ratio = price / eth_price
        else:
            ratio = price  # Already in USD, peg is $1

        logger.info("%s price: $%s, ratio vs %s: %s", asset.symbol, price, asset.underlying, ratio)

        if ratio < DEFILLAMA_DEPEG_THRESHOLD:
            if asset.protocol == LRT_PROTOCOL:
                depegged_lrt.append((asset.symbol, ratio))
            else:
                depegged_stables.append((asset.symbol, ratio))

    _send_depeg_alerts(depegged_lrt, LRT_PROTOCOL, "DefiLlama", DEFILLAMA_DEPEG_THRESHOLD)
    _send_depeg_alerts(depegged_stables, STABLES_PROTOCOL, "DefiLlama", DEFILLAMA_DEPEG_THRESHOLD)


def _send_depeg_alerts(depegged: list[tuple[str, Decimal]], protocol: str, source: str, threshold: Decimal) -> None:
    """Send CRITICAL alert listing all depegged assets."""
    if not depegged:
        return
    lines = [f"*{symbol}*: {value:.4f}" for symbol, value in depegged]
    message = f"Depeg detected ({source}, below {threshold}):\n" + "\n".join(lines)
    send_alert(Alert(AlertSeverity.CRITICAL, message, protocol))


def main() -> None:
    """Run depeg monitoring for all tracked assets."""
    logger.info("Starting depeg monitoring...")
    check_oracle_assets()
    check_defillama_assets()
    logger.info("Depeg monitoring complete.")


if __name__ == "__main__":
    main()
