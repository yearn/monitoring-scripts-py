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
COMPOUND_URL = "https://compound.blue"

GRAPH_BY_CHAIN = {
    Chain.POLYGON: "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/EhFokmwryNs7qbvostceRqVdjc3petuD13mmdUiMBw8Y",
}

# Map vaults by chain
VAULTS_BY_CHAIN = {
    Chain.POLYGON: [
        ["Compound WETH", "0xF5C81d25ee174d83f1FD202cA94AE6070d073cCF", 1],
        ["Compound USDC", "0x781FB7F6d845E3bE129289833b04d43Aa8558c42", 2],
        ["Compound USDT", "0xfD06859A671C21497a2EB8C5E3fEA48De924D6c8", 1],
    ]
}

MARKETS_RISK_1 = {
    Chain.POLYGON: [
        "0xb8ae474af3b91c8143303723618b31683b52e9c86566aa54c06f0bc27906bcae",  # wstETH/WETH -> lltv 91.5%, oracle: Chainlink wstETH-stETH Exchange Rate
        "0xa5b7ae7654d5041c28cb621ee93397394c7aee6c6e16c7e0fd030128d87ee1a3",  # WETH/USDC -> lltv 86%, oracle: Chainlink ETH/USD but there is no oracle for USDC/USD
        "0x01550b8779f4ca978fc16591537f3852c02c3491f597db93d9bb299dcbf5ddbe",  # WETH/USDT -> lltv 86%, oracle: Chainlink ETH/USD but there is no oracle for USDT/USD
        "0x1cfe584af3db05c7f39d60e458a87a8b2f6b5d8c6125631984ec489f1d13553b",  # WBTC/USDC -> lltv 86%, oracle: Chainlink WBTC/USD but there is no oracle for USDC/USD
        "0x2476bb905e3d94acd7b402b3d70d411eeb6ace82afd3007da69a0d5904dfc998",  # WBTC/USDT -> lltv 86%, oracle: Chainlink WBTC/USD but there is no oracle for USDT/USD
        "0x9eacb622c6ef9c2f0fa5f1fda58a8702eb8132d8f49783f6eea6acc3a398e741",  # WBTC/ETH-> lltv 86%, oracle: Chainlink BTC/USD and ETH/USD
        "0x267f344f5af0d85e95f253a2f250985a9fb9fca34a3342299e20c83b6906fc80",  # WPOL/USDT -> lltv 77%, oracle: Chainlink WPOL/USD, but there is no oracle for USDT/USD
        "0x7506b33817b57f686e37b87b5d4c5c93fdef4cffd21bbf9291f18b2f29ab0550",  # WPOL/USDC -> lltv 77%, oracle: Chainlink WPOL/USD, but there is no oracle for USDC/USD
    ],
}

MARKETS_RISK_2 = {
    Chain.POLYGON: [
        "0xd1485762dd5256b99530b6b07ab9d20c8d31b605dd5f27ad0c6dec2a18179ac6",  # compWETH/USDC -> lltv 86%, oracle: Chainlink ETH/USD and vault conversion rate for compoundWETH metamorpho vault
        "0xa8c2e5b31d1f3fb6c000bd49355d091f71e7c866fcb74a1cb2562ef67157bc2a",  # compWETH/USDT -> lltv 86%, oracle: Chainlink ETH/USD and vault conversion rate for compoundWETH metamorpho vault
        "0x41e537c46cc0e2f82aa69107cd72573f585602d8c33c9b440e08eaba5e8fded1",  # MATICX/USDT -> lltv 77%, oracle: Chainlink Calculated MaticX / USD, but there is no oracle for USDT/USD. Maticx has liquidity around 7M without slippage, around 1.7M USD. Withdrawing Matic will take 90 checkpoints (2-3 days) as per Polygon's native unstaking
        "0x1947267c49c3629c5ed59c88c411e8cf28c4d2afdb5da046dc8e3846a4761794",  # MATICX/USDC -> lltv 77%, oracle: Chainlink Calculated MaticX / USD, but there is no oracle for USDC/USD. Maticx has liquidity around 7M without slippage, around 1.7M USD. Withdrawing Matic will take 90 checkpoints (2-3 days) as per Polygon's native unstaking
    ],
}

MARKETS_RISK_3 = {
    Chain.POLYGON: [
        "0x8513df298cab92cafba1bae394420b7150aa40a5fac649c7168404bd5174a54c",  # sACRED/USDC -> lltv 86%, oracle: Redstone ACRED/USD which is connect only to securitize-api. Using vault conversion rate for sACRED/ACRED
    ],
}

MARKETS_RISK_4 = {Chain.POLYGON: []}

MARKETS_RISK_5 = {Chain.POLYGON: []}

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
    1: 1.20,  # Risk tier 1 max total risk
    2: 2.30,  # Risk tier 2 max total risk
    3: 3.40,  # Risk tier 3 max total risk
    4: 4.50,  # Risk tier 4 max total risk
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
    return f"{COMPOUND_URL}/borrow/{market_id}"


def get_vault_url(vault_address: str) -> str:
    """Generate URL for a Morpho vault."""
    return f"{COMPOUND_URL}/{vault_address}"


def check_high_allocation(vault_data, chain: Chain):
    """
    Send telegram message if high allocation is detected in any market.
    Send another message if total risk level is too high.
    """
    total_assets = int(vault_data["lastTotalAssets"])
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
        market_supply = int(market["totalSupply"])
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
        send_telegram_message(f"🚨 Problem with fetching data for Morpho markets: {str(e)} 🚨", PROTOCOL)
        return

    data = response.json()
    if "errors" in data:
        error_msg = data["errors"][0]["message"] if data["errors"] else "Unknown GraphQL error"
        send_telegram_message(f"🚨 GraphQL error when fetching Morpho data: {error_msg} 🚨", PROTOCOL)
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
    check_graph_data_for_chain(Chain.POLYGON)
