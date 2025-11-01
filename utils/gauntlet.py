import re
from datetime import datetime, timedelta

import requests

# Common supply assets and risk tiers used across protocols
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
    ["tBTC", 2],  # Uses chainlink oracle tBTC/USD
    ["sFRAX", 2],
    [
        "ezETH",
        2,
    ],  # Rate ezETH/WETH and chainlink WETH/USD https://www.llamarisk.com/research/risk-collateral-risk-assessment-renzo-restaked-eth-ezeth
    [
        "weETH",
        2,
    ],  # Rate weeth/WETH and chainlink WETH/USD https://www.llamarisk.com/research/risk-collateral-risk-assessment-wrapped-etherfi-eth-weeth
    ["rsETH", 2],  # Rate rsETH/WETH and chainlink WETH/USD
    ["LBTC", 2],  # Uses chainlink oracle LBTC/BTC and BTC/USD
    ["wOETH", 2],  # Origin ETH
    ["pufETH", 2],  # pufETH
    ["WPOL", 2],
    ["MaticX", 2],  # MaticX
    ["stMATIC", 2],  # stMATIC
    # Risk Tier 3
    ["USD0", 3],  # pyth oracle USD0/USD and medium liquidity (6M)
    ["deUSD", 3],
    ["sdeUSD", 3],
    ["osETH", 3],  # StakeWise osETH
    ["tETH", 3],  # Treehouse tETH
    ["SKY", 3],
    ["UNI", 3],
    ["LINK", 3],
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

# Common debt/supply ratio threshold
DEBT_SUPPLY_RATIO = 0.60  # 60%


def get_gauntlet_build_id() -> str | None:
    """Get the latest build ID from Gauntlet dashboard"""
    try:
        # Request the main page first to get the latest build ID
        response = requests.get("https://dashboards.gauntlet.xyz/")
        response.raise_for_status()

        # Find the build ID in the HTML
        # It's usually in a script tag with id="__NEXT_DATA__"
        build_id = re.search(r'"buildId":"([^"]+)"', response.text)
        if build_id:
            return build_id.group(1)
    except Exception as e:
        print(f"🚨 Error fetching Gauntlet build ID: {str(e)}")
    return None


def get_markets_for_protocol(protocol, max_retries=3) -> list[dict]:
    base_url = "https://dashboards.gauntlet.xyz/_next/data/{}/protocols/{}.json?protocolSlug={}"

    for attempt in range(max_retries):
        try:
            # Get the latest build ID
            build_id = get_gauntlet_build_id()
            if not build_id:
                # or return []
                raise Exception("Failed to get build ID")

            # Construct the URL with the latest build ID
            protocol_lower = protocol.lower()
            urlHealthMetrics = base_url.format(build_id, protocol_lower, protocol_lower)

            response = requests.get(urlHealthMetrics)
            response.raise_for_status()
            data = response.json()

            # If we get here, the request was successful
            # Continue with the existing logic
            markets = data["pageProps"]["protocolPage"]["markets"]
            return markets

        except requests.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                print(f"🚨 Error fetching Gauntlet metrics after {max_retries} attempts: {str(e)}")
                return []
            print(f"Attempt {attempt + 1} failed, retrying...")
            continue
        except ValueError as e:
            print(f"🚨 Error parsing Gauntlet JSON response: {str(e)}")
            return []
        except Exception as e:
            print(f"🚨 Unexpected error: {str(e)}")
            return []


def get_charts_for_protocol_market(protocol, market, max_retries=3):
    base_url = "https://dashboards.gauntlet.xyz/_next/data/{}/protocols/{}/markets/{}.json"

    for attempt in range(max_retries):
        try:
            # Get the latest build ID
            build_id = get_gauntlet_build_id()
            if not build_id:
                raise Exception("Failed to get build ID")

            protocol_lower = protocol.lower()
            urlCharts = base_url.format(build_id, protocol_lower, market)

            response = requests.get(urlCharts)
            response.raise_for_status()
            data = response.json()

            # this is used only for euler, if there are more protocols, we need to change this
            # response has ["scalarCards"] and ["charts"]
            return data["pageProps"]["chartSections"][0]

        except requests.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                print(f"🚨 Error fetching Gauntlet charts after {max_retries} attempts: {str(e)}")
                return []
            print(f"Attempt {attempt + 1} failed, retrying...")
            continue
        except ValueError as e:
            print(f"🚨 Error parsing Gauntlet JSON response: {str(e)}")
            return []
        except Exception as e:
            print(f"🚨 Unexpected error: {str(e)}")
            return []


def get_timestamp_before(hours: int):
    """Get timestamp from one hour ago in ISO format"""
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=hours)
    return one_hour_ago.strftime("%Y-%m-%dT%H:00:00.000Z")


def format_usd(number: float) -> str:
    """Format number to readable USD string with K, M, B suffixes"""
    if number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"${number / 1_000:.2f}K"
    return f"${number:.2f}"


def get_market_allocation_threshold(market_risk_level, vault_risk_level) -> float:
    """
    Get allocation threshold based on market and vault risk levels.
    For higher vault risk levels, thresholds shift up (become more permissive).
    For example, if vault risk level is 2, then market risk level 1 is 0.80, market risk level 2 is 0.30, etc.
    """
    # Shift market risk level down based on vault risk level
    adjusted_risk = max(1, market_risk_level - (vault_risk_level - 1))
    return ALLOCATION_TIERS[adjusted_risk]


def fetch_borrow_metrics_from_gauntlet(protocol, market_key, vault_risk_level) -> list[str]:
    """
    Fetch and analyze market allocation metrics from Gauntlet.
    Returns a list of alert messages if any thresholds are exceeded.
    """
    alerts = []
    charts = get_charts_for_protocol_market(protocol, market_key)
    if not charts:
        alerts.append(f"🚨 Market {market_key} charts cannot be fetched")
        return alerts

    cards = charts["scalarCards"]
    total_supply = cards[0]["value"]["amount"]
    total_borrow = cards[1]["value"]["amount"]
    last_updated = cards[0]["lastUpdated"]

    old_data_threshold = 36  # hours is the max time for a market to be updated
    if last_updated < get_timestamp_before(hours=old_data_threshold):
        alerts.append(
            f"🚨 Market {market_key} is not updated for {old_data_threshold} hours. Last updated at {last_updated}"
        )
        return alerts

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
                asset_risk_tier = SUPPLY_ASSETS_DICT.get(asset, 5)  # Default to tier 5 if asset not found
                allocation_threshold = get_market_allocation_threshold(asset_risk_tier, vault_risk_level)

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

    print("--------------------------------")
    print(f"Total risk level: {total_risk_level:.1%}")
    print("\n================================\n")

    return alerts
