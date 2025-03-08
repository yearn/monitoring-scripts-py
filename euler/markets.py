from utils.gauntlet import (
    format_usd,
    get_charts_for_protocol_market,
    get_markets_for_protocol,
    get_timestamp_before,
)
from utils.telegram import send_telegram_message

PROTOCOL = "EULER"
DEBT_SUPPLY_RATIO = 0.60  # 60%
# available markets: https://dashboards.gauntlet.xyz/protocols/euler
USED_EULER_VAULTS_KEYS = [
    ["ethereum-prime", 2],
    # ["ethereum-yield", 3], No active strategy for this vault
]

SUPPLY_ASSETS = [
    # Risk Tier 1
    ["USDC", 1],
    ["USDT", 1],
    ["DAI", 1],
    ["USDS", 1],
    ["sUSDS", 1],
    ["WETH", 1],
    ["WBTC", 1],
    ["mETH", 1],  # Pyth oracle mETH/ETH and chainlink ETH/USD
    ["cbETH", 1],  # Rate cbETH/WETH and chainlink WETH/USD
    ["rETH", 1],  # Rate rETH/WETH and chainlink WETH/USD
    ["wstETH", 1],  # Rate wstETH/WETH and chainlink WETH/USD
    ["cbBTC", 1],  # Chainlink oracle cbBTC/USD
    # Risk Tier 2
    [
        "ETHx",
        2,
    ],  # Rate ETHx/WETH and chainlink WETH/USD https://www.llamarisk.com/research/risk-addendum-to-collateral-risk-assessment-stader-ethx
    ["sUSDe", 2],  # Rate sUSDe/USDe and chainlink USDe/USD
    ["PT-USDe-27MAR2025", 2],  # Pendle PT to USDe and chainlink USDe/USD
    ["PT-sUSDE-27MAR2025", 2],  # Pendle PT to USDe and chainlink USDe/USD
    ["PT-sUSDE-29MAY2025", 2],  # Pendle PT to USDe and chainlink USDe/USD
    ["PYUSD", 2],  # Pyth oracle PYUSD/USD and high liquidity (10M)
    # Risk Tier 3
    ["tBTC", 3],  # Uses chainlink oracle tBTC/USD
    [
        "ezETH",
        3,
    ],  # Rate ezETH/WETH and chainlink WETH/USD https://www.llamarisk.com/research/risk-collateral-risk-assessment-renzo-restaked-eth-ezeth
    [
        "weETH",
        3,
    ],  # Rate weeth/WETH and chainlink WETH/USD https://www.llamarisk.com/research/risk-collateral-risk-assessment-wrapped-etherfi-eth-weeth
    ["rsETH", 3],  # Rate rsETH/WETH and chainlink WETH/USD
    ["LBTC", 3],  # Uses chainlink oracle LBTC/BTC and BTC/USD
    ["USD0", 3],  # pyth oracle USD0/USD and medium liquidity (6M)
    # Risk Tier 4
    [
        "wUSDM",
        4,
    ],  # Rate wusdm/WETH and fixed rate USDM/USD https://www.llamarisk.com/research/archive-llamarisk-asset-risk-assessment-mountain-protocol-usdm - https://mountainprotocol.com/usdm
    ["eBTC", 4],  # Rate eBTC/BTC and chainlink BTC/USD
    [
        "SolvBTC",
        4,
    ],  # Uses chainlink oracle solvBTC/BTC and BTC/USD https://solv.finance/
    # Risk Tier 5
    [
        "USD0++",
        5,
    ],  # pyth oracle USD0++/USD but low liquidity to get usd0, below 1M without slippage and euler market size is 4M
    ["FDUSD", 5],  # pyth oracle FDUSD/USD and low liquidity (100k)
    ["mTBILL", 5],  # Euler Vault uses fixed rate oracle. https://midas.app/
    ["wM", 5],  # Euler Vault uses fixed rate oracle. https://www.m0.org/
    ["mBASIS", 5],
]

# Convert SUPPLY_ASSETS list to dictionary for easier lookup
SUPPLY_ASSETS_DICT = {asset: risk_tier for asset, risk_tier in SUPPLY_ASSETS}

# Define base allocation tiers
ALLOCATION_TIERS = {
    1: 1.01,  # Risk tier 1 max allocation
    2: 0.30,  # Risk tier 2 max allocation
    3: 0.10,  # Risk tier 3 max allocation
    4: 0.05,  # Risk tier 4 max allocation
    5: 0.01,  # Unknown market max allocation
}

# Define max risk thresholds by risk level
MAX_RISK_THRESHOLDS = {
    1: 1.10,  # Risk tier 1 max total risk
    2: 2.20,  # Risk tier 2 max total risk
    3: 3.30,  # Risk tier 3 max total risk
    4: 4.40,  # Risk tier 4 max total risk
    5: 5.00,  # Risk tier 5 max total risk
}


def fetch_metric_from_gauntlet(max_retries=3):
    alerts = []
    markets = get_markets_for_protocol(PROTOCOL, max_retries)

    if not markets:
        return False

    for market in markets:
        if market["key"] in USED_EULER_VAULTS_KEYS:
            market_data = market["data"]
            last_updated = market_data["borrow"]["lastUpdated"]
            if last_updated < get_timestamp_before(hours=6):
                alerts.append(
                    f"🚨 Market is not updated for {market['label']} - last updated {last_updated}"
                )
                break

            borrow_amount = market_data["borrow"]["amount"]
            supply_amount = market_data["supply"]["amount"]
            debt_supply_ratio = (
                borrow_amount / supply_amount if supply_amount > 0 else 0
            )
            if debt_supply_ratio > DEBT_SUPPLY_RATIO:
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"📈 Debt/Supply Ratio: {debt_supply_ratio:.2%}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

            # VaR conveys capital at risk due to insolvencies when markets are under duress (i.e., Black Thursday)
            value_at_risk = market_data["var"]["amount"]
            if value_at_risk / borrow_amount > 0.01:  # 1%
                # for more info check: https://www.gauntlet.xyz/resources/improved-var-methodology
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"💸 Value at Risk: {format_usd(value_at_risk)}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

            # LaR conveys capital at risk due to liquidations when markets are under duress.
            liquidation_at_risk = market_data["lar"]["amount"]
            if liquidation_at_risk / borrow_amount > 0.05:  # 5%
                # for more info check: https://www.gauntlet.xyz/resources/improved-var-methodology
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"💸 Liquidation at Risk: {format_usd(liquidation_at_risk)}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)

    return True


# reused from morpho/markets.py
def get_market_allocation_threshold(market_risk_level, vault_risk_level):
    """
    Get allocation threshold based on market and vault risk levels.
    For higher vault risk levels, thresholds shift up (become more permissive).
    For example, if vault risk level is 2, then market risk level 1 is 0.80, market risk level 2 is 0.30, etc.
    """
    # Shift market risk level down based on vault risk level
    adjusted_risk = max(1, market_risk_level - (vault_risk_level - 1))
    return ALLOCATION_TIERS[adjusted_risk]


def fetch_borrow_metrics_from_gauntlet(market_key, vault_risk_level):
    alerts = []
    charts = get_charts_for_protocol_market(PROTOCOL, market_key)
    cards = charts["scalarCards"]
    total_supply = cards[0]["value"]["amount"]
    total_borrow = cards[1]["value"]["amount"]
    last_updated = cards[0]["lastUpdated"]
    if last_updated < get_timestamp_before(hours=12):
        # TODO: verify how long it takes for the market to be updated
        send_telegram_message(
            f"🚨 Market {market_key} is not updated for 12 hours. Last updated at {last_updated}",
            PROTOCOL,
        )
        return

    charts = charts["charts"]
    total_risk_level = 0.0
    print(f"Market: {market_key}")
    print(f"Assigned Risk Level: {vault_risk_level}")
    print(f"Total supply: {format_usd(total_supply)}")
    print(f"Total borrow: {format_usd(total_borrow)}")
    print("--------------------------------")
    print("Asset | Supply | Allocation")

    for chart in charts:
        if chart["key"] == "market_health_timeseries_asset_supply":
            # reverse the data so we get the biggest markets/vaults first
            for data in reversed(chart["data"]):
                asset = data["id"]
                supply = data["data"][-1]["y"]
                if supply == 0:
                    continue

                # Use dictionary lookup instead of list indexing
                asset_risk_tier = SUPPLY_ASSETS_DICT.get(
                    asset, 5
                )  # Default to tier 5 if asset not found
                allocation_threshold = get_market_allocation_threshold(
                    asset_risk_tier, vault_risk_level
                )

                # Calculate allocation ratio
                allocation_ratio = supply / total_supply if total_supply > 0 else 0

                # Check if allocation exceeds threshold
                if allocation_ratio > allocation_threshold:
                    alerts.append(
                        f"🔺 High allocation detected for {asset} in market {market_key}\n"
                        f"💹 Current allocation: {allocation_ratio:.1%}\n"
                        f"📊 Max acceptable allocation: {allocation_threshold:.1%}\n"
                        f"💰 Supply amount: {format_usd(supply)}"
                    )

                # Calculate risk contribution
                risk_multiplier = asset_risk_tier
                total_risk_level += risk_multiplier * allocation_ratio
                print(f"{asset} | {format_usd(supply)} | {allocation_ratio:.1%}")

    # Check total risk level against threshold for vault risk level
    if total_risk_level > MAX_RISK_THRESHOLDS[vault_risk_level]:
        alerts.append(
            f"🔺 High total risk level detected in market {market_key}:\n"
            f"📊 Total risk level: {total_risk_level:.1%}\n"
            f"📈 Max acceptable risk: {MAX_RISK_THRESHOLDS[vault_risk_level]:.1%}\n"
            f"💰 Total assets: {format_usd(total_supply)}"
        )

    if total_borrow / total_supply > DEBT_SUPPLY_RATIO:
        alerts.append(
            f"🔺 High borrow/supply ratio detected in market {market_key}:\n"
            f"📊 Total borrow/supply ratio: {total_borrow / total_supply:.1%}\n"
            f"💰 Total assets: {format_usd(total_supply)}\n"
            f"💸 Total borrow: {format_usd(total_borrow)}\n"
        )

    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)

    print("--------------------------------")
    print(f"Total risk level: {total_risk_level:.1%}")
    print("\n================================\n")


def main():
    successfull = fetch_metric_from_gauntlet()
    if not successfull:
        # if both data sources are not working, send an alert
        send_telegram_message("🚨 Euler metrics cannot be fetched", PROTOCOL)

    # Implement checks for vault allocations with their respective risk levels
    for vault in USED_EULER_VAULTS_KEYS:
        fetch_borrow_metrics_from_gauntlet(vault[0], vault[1])


if __name__ == "__main__":
    main()
