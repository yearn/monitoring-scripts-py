"""
On-chain Compound V3 collateral risk monitoring.

Reads collateral data directly from Comet contracts instead of relying on
Gauntlet's dashboard API (which can have stale data 36h+).

For each Compound V3 market:
- Discovers collateral assets and their on-chain balances & prices
- Calculates per-asset allocation ratios and weighted risk levels
- Checks borrow/supply ratio
- Detects bad debt (negative reserves)

Sends Telegram alerts when thresholds are exceeded.
"""

from dataclasses import dataclass

from utils.abi import load_abi
from utils.assets import (
    ALLOCATION_TIERS,
    DEBT_SUPPLY_RATIO,
    MAX_RISK_THRESHOLDS,
    SUPPLY_ASSETS_DICT,
    get_market_allocation_threshold,
)
from utils.chains import Chain
from utils.formatting import format_usd
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "comp"
logger = get_logger(PROTOCOL)

PRICE_SCALE = 1e8  # Compound V3 prices use 8 decimal places (Chainlink format)

ABI_COMET = load_abi("compound/abi/CTokenV3.json")
ABI_ERC20 = load_abi("common-abi/ERC20.json")

# (address, name, risk_level) per chain
# Risk levels match the Gauntlet vault risk levels used in ALLOCATION_TIERS
MARKETS_BY_CHAIN: dict[Chain, list[tuple[str, str, int]]] = {
    Chain.MAINNET: [
        ("0xc3d688B66703497DAA19211EEdff47f25384cdc3", "cUSDCv3", 1),
        ("0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840", "cUSDTv3", 1),
        ("0xA17581A9E3356d9A858b789D68B4d866e593aE94", "cWETHv3", 1),
        ("0x5D409e56D886231aDAf00c8775665AD0f9897b56", "cUSDSv3", 2),
    ],
}


@dataclass
class CollateralAsset:
    """On-chain collateral asset data for a Compound V3 market."""

    symbol: str
    address: str
    price_feed: str
    scale: int
    borrow_collateral_factor: float
    liquidate_collateral_factor: float
    supply_cap: int
    total_supply_raw: int
    price_raw: int

    @property
    def usd_value(self) -> float:
        """Calculate USD value of total collateral supplied."""
        return self.total_supply_raw * self.price_raw / (self.scale * PRICE_SCALE)


@dataclass
class MarketData:
    """Aggregated on-chain data for a Compound V3 market."""

    name: str
    address: str
    risk_level: int
    base_scale: int
    base_price_raw: int
    total_supply_raw: int
    total_borrow_raw: int
    reserves_raw: int  # signed: negative = bad debt
    collaterals: list[CollateralAsset]

    @property
    def total_supply_usd(self) -> float:
        return self.total_supply_raw * self.base_price_raw / (self.base_scale * PRICE_SCALE)

    @property
    def total_borrow_usd(self) -> float:
        return self.total_borrow_raw * self.base_price_raw / (self.base_scale * PRICE_SCALE)

    @property
    def reserves_usd(self) -> float:
        return self.reserves_raw * self.base_price_raw / (self.base_scale * PRICE_SCALE)

    @property
    def total_collateral_usd(self) -> float:
        return sum(c.usd_value for c in self.collaterals)


def _fetch_markets_data(chain: Chain) -> list[MarketData]:
    """Fetch on-chain data for all Compound V3 markets on a chain.

    Uses 3 batch rounds to minimize RPC calls:
    1. numAssets + base market metrics for all markets
    2. getAssetInfo(i) for all discovered asset indices
    3. totalsCollateral, getPrice, symbol for all assets + base price
    """
    markets = MARKETS_BY_CHAIN.get(chain, [])
    if not markets:
        return []

    client = ChainManager.get_client(chain)

    # --- Batch 1: market-level data ---
    with client.batch_requests() as batch:
        for address, _, _ in markets:
            comet = client.eth.contract(address=address, abi=ABI_COMET)
            batch.add(comet.functions.numAssets())
            batch.add(comet.functions.totalSupply())
            batch.add(comet.functions.totalBorrow())
            batch.add(comet.functions.getReserves())
            batch.add(comet.functions.baseTokenPriceFeed())
            batch.add(comet.functions.baseScale())
        responses_1 = client.execute_batch(batch)

    # Parse batch 1: 6 calls per market
    calls_per_market = 6
    market_basics: list[dict] = []
    for i, (address, name, risk_level) in enumerate(markets):
        offset = i * calls_per_market
        market_basics.append(
            {
                "address": address,
                "name": name,
                "risk_level": risk_level,
                "num_assets": int(responses_1[offset]),
                "total_supply": int(responses_1[offset + 1]),
                "total_borrow": int(responses_1[offset + 2]),
                "reserves": int(responses_1[offset + 3]),
                "base_price_feed": responses_1[offset + 4],
                "base_scale": int(responses_1[offset + 5]),
            }
        )

    # --- Batch 2: getAssetInfo for all assets across all markets ---
    with client.batch_requests() as batch:
        for mb in market_basics:
            comet = client.eth.contract(address=mb["address"], abi=ABI_COMET)
            for asset_idx in range(mb["num_assets"]):
                batch.add(comet.functions.getAssetInfo(asset_idx))
        responses_2 = client.execute_batch(batch)

    # Parse batch 2: extract asset addresses and price feeds
    asset_infos: list[list[tuple]] = []  # per market, list of AssetInfo tuples
    idx = 0
    for mb in market_basics:
        market_asset_infos = []
        for _ in range(mb["num_assets"]):
            # AssetInfo: (offset, asset, priceFeed, scale, borrowCF, liquidateCF, liquidationFactor, supplyCap)
            market_asset_infos.append(responses_2[idx])
            idx += 1
        asset_infos.append(market_asset_infos)

    # --- Batch 3: totalsCollateral, getPrice, symbol for each asset + base price ---
    with client.batch_requests() as batch:
        for i, mb in enumerate(market_basics):
            comet = client.eth.contract(address=mb["address"], abi=ABI_COMET)
            # Base token price
            batch.add(comet.functions.getPrice(mb["base_price_feed"]))
            # Per-asset calls
            for info in asset_infos[i]:
                asset_address = info[1]
                price_feed = info[2]
                batch.add(comet.functions.totalsCollateral(asset_address))
                batch.add(comet.functions.getPrice(price_feed))
                erc20 = client.eth.contract(address=asset_address, abi=ABI_ERC20)
                batch.add(erc20.functions.symbol())
        responses_3 = client.execute_batch(batch)

    # Parse batch 3 and build MarketData objects
    results: list[MarketData] = []
    idx = 0
    for i, mb in enumerate(market_basics):
        base_price_raw = int(responses_3[idx])
        idx += 1

        collaterals: list[CollateralAsset] = []
        for info in asset_infos[i]:
            # totalsCollateral returns (totalSupplyAsset, _reserved)
            totals = responses_3[idx]
            total_supply_asset = int(totals[0])
            idx += 1

            price_raw = int(responses_3[idx])
            idx += 1

            symbol = responses_3[idx]
            idx += 1

            collaterals.append(
                CollateralAsset(
                    symbol=symbol,
                    address=info[1],
                    price_feed=info[2],
                    scale=int(info[3]),
                    borrow_collateral_factor=int(info[4]) / 1e18,
                    liquidate_collateral_factor=int(info[5]) / 1e18,
                    supply_cap=int(info[7]),
                    total_supply_raw=total_supply_asset,
                    price_raw=price_raw,
                )
            )

        results.append(
            MarketData(
                name=mb["name"],
                address=mb["address"],
                risk_level=mb["risk_level"],
                base_scale=mb["base_scale"],
                base_price_raw=base_price_raw,
                total_supply_raw=mb["total_supply"],
                total_borrow_raw=mb["total_borrow"],
                reserves_raw=mb["reserves"],
                collaterals=collaterals,
            )
        )

    return results


def _analyze_market(market: MarketData) -> list[str]:
    """Analyze a single market's collateral risk. Returns list of alert messages."""
    alerts: list[str] = []
    total_collateral_usd = market.total_collateral_usd

    if total_collateral_usd == 0:
        logger.info("Market %s has no collateral", market.name)
        return alerts

    logger.info("Market: %s (risk level %d)", market.name, market.risk_level)
    logger.info("Total supply: %s", format_usd(market.total_supply_usd))
    logger.info("Total borrow: %s", format_usd(market.total_borrow_usd))
    logger.info("Total collateral: %s", format_usd(total_collateral_usd))
    logger.debug("--------------------------------")
    logger.debug("Asset | Supply | Allocation")

    total_risk_level = 0.0
    unknown_assets: list[str] = []

    for c in sorted(market.collaterals, key=lambda x: x.usd_value, reverse=True):
        if c.usd_value == 0:
            continue

        asset_risk_tier: int = int(SUPPLY_ASSETS_DICT.get(c.symbol, 5))  # type: ignore[call-overload]
        if c.symbol not in SUPPLY_ASSETS_DICT:
            unknown_assets.append(c.symbol)

        allocation_ratio = c.usd_value / total_collateral_usd
        allocation_threshold = get_market_allocation_threshold(asset_risk_tier, market.risk_level)

        if allocation_ratio > allocation_threshold:
            alerts.append(
                f"🔺 High allocation detected for {c.symbol} in market {market.name}\n"
                f"💹 Current allocation: {allocation_ratio:.1%}\n"
                f"📊 Max acceptable allocation: {allocation_threshold:.1%}\n"
                f"💰 Supply amount: {format_usd(c.usd_value)}"
            )

        risk_multiplier = asset_risk_tier
        total_risk_level += risk_multiplier * allocation_ratio
        logger.debug("%s | %s | %s", c.symbol, format_usd(c.usd_value), f"{allocation_ratio:.1%}")

    # Check total risk level
    max_risk = MAX_RISK_THRESHOLDS.get(market.risk_level, MAX_RISK_THRESHOLDS[max(ALLOCATION_TIERS.keys())])
    if total_risk_level > max_risk:
        alerts.append(
            f"🔺 High total risk level detected in market {market.name}:\n"
            f"📊 Total risk level: {total_risk_level:.1%}\n"
            f"📈 Max acceptable risk: {max_risk:.1%}\n"
            f"💰 Total collateral: {format_usd(total_collateral_usd)}"
        )

    # Check borrow/supply ratio
    if market.total_supply_usd > 0 and market.total_borrow_usd / market.total_supply_usd > DEBT_SUPPLY_RATIO:
        ratio = market.total_borrow_usd / market.total_supply_usd
        alerts.append(
            f"🔺 High borrow/supply ratio detected in market {market.name}:\n"
            f"📊 Total borrow/supply ratio: {ratio:.1%}\n"
            f"💰 Total supply: {format_usd(market.total_supply_usd)}\n"
            f"💸 Total borrow: {format_usd(market.total_borrow_usd)}"
        )

    # Check bad debt (negative reserves)
    if market.reserves_raw < 0:
        bad_debt_usd = abs(market.reserves_usd)
        alerts.append(
            f"🚨 Bad debt detected in market {market.name}:\n"
            f"💀 Bad debt: {format_usd(bad_debt_usd)}\n"
            f"💰 Total supply: {format_usd(market.total_supply_usd)}\n"
            f"💸 Total borrow: {format_usd(market.total_borrow_usd)}"
        )

    # Alert on unknown assets
    if unknown_assets:
        alerts.append(
            f"⚠️ Unknown collateral assets in market {market.name}: {', '.join(unknown_assets)}\n"
            "Please update SUPPLY\\_ASSETS in utils/assets.py"
        )

    logger.info("Total risk level: %s", f"{total_risk_level:.1%}")
    logger.info("Reserves: %s", format_usd(market.reserves_usd))
    logger.info("================================")

    return alerts


def check_collateral_risk(chain: Chain) -> None:
    """Check on-chain collateral risk for all Compound V3 markets on a chain.

    Fetches live data from Comet contracts and sends Telegram alerts
    if any risk thresholds are exceeded.
    """
    logger.info("Checking on-chain collateral risk for %s...", chain.name)
    markets_data = _fetch_markets_data(chain)

    for market in markets_data:
        alerts = _analyze_market(market)
        if alerts:
            message = "\n\n".join(alerts)
            send_telegram_message(message, PROTOCOL)
