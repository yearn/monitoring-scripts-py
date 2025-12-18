"""
Morpho markets monitoring script.
Get data from The Graph API.

This module checks Morpho markets for:
1. Bad debt
2. High allocation levels
3. Low liquidity
"""

import os

import requests
from dotenv import load_dotenv

from utils.chains import Chain
from utils.telegram import send_telegram_message

# Load environment variables from .env file
load_dotenv()

# Configuration constants
PROTOCOL = "MORPHO"
BAD_DEBT_RATIO = 0.005  # 0.5% of total borrowed tvl
LIQUIDITY_THRESHOLD = 0.01  # 1% of total assets
MARKET_URL = "https://compound.blue"

GRAPH_BY_CHAIN = {}

# Map vaults by chain
VAULTS_BY_CHAIN = {}

MARKETS_RISK_1 = {}

MARKETS_RISK_2 = {}

MARKETS_RISK_3 = {}

MARKETS_RISK_4 = {}

MARKETS_RISK_5 = {}

# Define base allocation tiers
ALLOCATION_TIERS = {
    1: 1.01,  # Risk tier 1 max allocation # TODO: think about lowering this to 0.80 but some vaults use 100% allocation to one market
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


def get_market_allocation_threshold(market_risk_level: int, vault_risk_level: int) -> float:
    """
    Get allocation threshold based on market and vault risk levels.
    For higher vault risk levels, thresholds shift up (become more permissive).
    For example, if vault risk level is 2, then market risk level 1 is 0.80, market risk level 2 is 0.30, etc.

    Args:
        market_risk_level: Risk level of the market (1-5)
        vault_risk_level: Risk level of the vault (1-5)

    Returns:
        Allocation threshold as a decimal (0-1)
    """
    # Shift market risk level down based on vault risk level
    adjusted_risk = max(1, market_risk_level - (vault_risk_level - 1))
    return ALLOCATION_TIERS[adjusted_risk]


def get_market_url(market_id: str) -> str:
    """Generate URL for a Morpho market."""
    return f"{MARKET_URL}/borrow/{market_id}"


def get_vault_url(vault_address: str) -> str:
    """Generate URL for a Morpho vault."""
    return f"{MARKET_URL}/{vault_address}"


def check_high_allocation(vault_data, chain: Chain):
    """
    Send telegram message if high allocation is detected in any market.
    Send another message if total risk level is too high.
    """
    total_assets = int(vault_data.get("lastTotalAssets", 0))
    if total_assets == 0:
        return

    vault_name = vault_data["name"]
    # Find vault in VAULTS_BY_CHAIN to get risk level
    vault_address = vault_data["id"]
    vault_url = get_vault_url(vault_address)
    risk_level = None
    for vault in VAULTS_BY_CHAIN[chain]:
        if vault[1].lower() == vault_address.lower():
            risk_level = vault[2]
            break

    if risk_level is None:
        # Throw error if vault not found in config
        raise ValueError(f"Vault {vault_address} not found in VAULTS_BY_CHAIN config")

    total_risk_level = 0.0
    decimals = 18
    symbol = ""

    for market_data in vault_data["markets"]:
        market = market_data["market"]
        makret_id = market["id"]
        market_supply = int(market.get("totalSupply", 0))
        allocation_ratio = market_supply / total_assets
        idle_market = market["inputToken"]["id"] == "0x0000000000000000000000000000000000000000"
        decimals = market["borrowedToken"]["decimals"]
        symbol = market["borrowedToken"]["symbol"]

        # Determine market risk level
        if makret_id in MARKETS_RISK_1[chain] or idle_market:
            market_risk_level = 1
        elif makret_id in MARKETS_RISK_2[chain]:
            market_risk_level = 2
        elif makret_id in MARKETS_RISK_3[chain]:
            market_risk_level = 3
        elif makret_id in MARKETS_RISK_4[chain]:
            market_risk_level = 4
        else:
            market_risk_level = 5

        allocation_threshold = get_market_allocation_threshold(market_risk_level, risk_level)
        risk_multiplier = market_risk_level

        if allocation_ratio > allocation_threshold:
            market_url = get_market_url(makret_id)
            market_name = f"{market['inputToken']['symbol']}/{market['borrowedToken']['symbol']}"
            message = (
                f"🔺 High allocation detected in [{vault_name}]({vault_url}) on {chain.name}\n"
                f"💹 Market [{market_name}]({market_url})\n"
                f"🔢 Allocation: {allocation_ratio:.1%} but max acceptable allocation is {allocation_threshold:.1%}\n"
            )
            send_telegram_message(message, PROTOCOL)

        # Calculate weighted risk score for each market allocation
        # risk_multiplier: market risk tier (1-5, higher = riskier)
        # allocation_ratio: percentage of vault's assets in this market
        # total_risk_level: sum of (risk_tier * allocation) across all markets
        total_risk_level += risk_multiplier * allocation_ratio

    # print total risk level and vault name
    print(f"Total risk level: {total_risk_level:.1%}, vault: {vault_name} on {chain.name}")
    if total_risk_level > MAX_RISK_THRESHOLDS[risk_level]:
        message = (
            f"🔺 High allocation detected in [{vault_name}]({vault_url}) on {chain.name}\n"
            f"🔢 Total risk level: {total_risk_level / 100:.3%} but max acceptable is {MAX_RISK_THRESHOLDS[risk_level]}\n"
            f"🔢 Total assets: {total_assets / 10**decimals:.2f} {symbol}\n"
        )
        send_telegram_message(message, PROTOCOL)


def check_low_liquidity(vault_data, chain: Chain):
    """
    Send telegram message if low liquidity is detected.
    """
    vault_name = vault_data["name"]
    vault_url = get_vault_url(vault_data["id"])
    total_assets = int(vault_data["lastTotalAssets"])
    if total_assets == 0:
        return

    decimals = 18
    symbol = ""
    liquidity = 0
    for market_data in vault_data["markets"]:
        market = market_data["market"]
        liquidity += int(market["totalSupply"]) - int(market["totalBorrow"])
        decimals = market["borrowedToken"]["decimals"]
        symbol = market["borrowedToken"]["symbol"]

    liquidity_ratio = liquidity / total_assets
    if liquidity_ratio < LIQUIDITY_THRESHOLD:
        message = (
            f"⚠️ Low liquidity detected in [{vault_name}]({vault_url}) on {chain.name}\n"
            f"💰 Liquidity: {liquidity_ratio:.1%} of total assets\n"
            f"💵 Liquidity: {liquidity / 10**decimals:.2f} {symbol}\n"
            f"📊 Total Assets: {total_assets / 10**decimals:.2f} {symbol}\n"
        )
        send_telegram_message(message, PROTOCOL)


def check_bad_debt(data):
    """
    Send telegram message if bad debt is detected in any market.
    """
    bad_debt_realizations = data.get("data", {}).get("badDebtRealizations", {})
    for realization in bad_debt_realizations:
        bad_debt_value = int(realization["badDebt"])
        market = realization["market"]
        # NOTE: change this when adding more chains
        if (
            market["id"] not in MARKETS_RISK_1[Chain.POLYGON]
            and market["id"] not in MARKETS_RISK_2[Chain.POLYGON]
            and market["id"] not in MARKETS_RISK_3[Chain.POLYGON]
        ):
            continue
        market_address = market["id"]
        total_borrow = int(market["totalBorrow"])
        ratio = bad_debt_value / total_borrow
        if ratio > BAD_DEBT_RATIO:
            market_url = get_market_url(market_address)
            market_name = f"{market['inputToken']['name']}/{market['borrowedToken']['name']}"
            message = (
                f"🚨 Bad debt detected for Market [{market_name}]({market_url})\n"
                f"💸 Bad debt: {bad_debt_value / 10 ** market['borrowedToken']['decimals']:.2f}\n"
                f"📊 Bad debt ratio: {ratio:.2%}\n"
            )
            send_telegram_message(message, PROTOCOL)


def check_graph_data_for_chain(chain: Chain):
    """
    Fetch data from Morpho API.
    Check markets on specific chain for low liquidity, high allocation and bad debt.
    Send telegram message if data cannot be fetched.
    """
    print(f"Checking Morpho markets with Graph API on {chain.name}...")

    # Collect all vault addresses from all chains
    vault_addresses = []
    for vault in VAULTS_BY_CHAIN[chain]:
        vault_addresses.append(vault[1])

    # Create a proper array format for GraphQL
    vault_addresses_array = "[" + ",".join(f'"{addr}"' for addr in vault_addresses) + "]"

    query = f"""
    {{
      metaMorphos(where: {{ id_in: {vault_addresses_array} }}) {{
        id
        name
        symbol
        decimals
        lastTotalAssets
        totalShares
        idle
        markets {{
          market {{
            id
            totalSupply
            totalBorrow
            totalCollateral
            inputToken {{
              symbol
              name
              id
            }}
            borrowedToken {{
              symbol
              name
              id
              decimals
            }}
          }}
        }}
        deposits(where: {{ metaMorpho_in: {vault_addresses_array} }}) {{
            amount
        }}
      }}
      badDebtRealizations {{
        id
        badDebt
        market {{
          id
          totalSupply
          totalBorrow
          inputToken {{
            symbol
            name
            id
          }}
          borrowedToken {{
            symbol
            name
            id
            decimals
          }}
        }}
      }}
    }}
    """

    api_key = os.getenv("GRAPH_API_KEY")
    if not api_key:
        raise ValueError("GRAPH_API_KEY environment variable is not set")
    api_url = GRAPH_BY_CHAIN[chain].format(api_key=api_key)

    json_data = {"query": query}
    try:
        response = requests.post(api_url, json=json_data, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        send_telegram_message(f"🚨 Problem with fetching data for Morpho markets: {str(e)} 🚨", PROTOCOL, True, True)
        return

    data = response.json()
    if "errors" in data:
        error_msg = data["errors"][0]["message"] if data["errors"] else "Unknown GraphQL error"
        if "indexing_error" in error_msg:
            print(f"🚨 GraphQL indexing error when fetching Morpho data: {error_msg} 🚨")
        else:
            send_telegram_message(f"🚨 GraphQL error when fetching Morpho data: {error_msg} 🚨", PROTOCOL, True, True)
        return

    vaults_data = data.get("data", {}).get("metaMorphos", {})
    if len(vaults_data) == 0:
        send_telegram_message("🚨 No vaults data found 🚨", PROTOCOL)
        return

    check_bad_debt(data)
    for vault in vaults_data:
        check_low_liquidity(vault, chain)
        check_high_allocation(vault, chain)
    return


if __name__ == "__main__":
    # TODO: define chain to check and add ci trigger
    # check_graph_data_for_chain(Chain.POLYGON)
    print("No chain defined")
