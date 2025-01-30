import requests
from utils.telegram import send_telegram_message
from utils.chains import Chain


API_URL = "https://blue-api.morpho.org/graphql"
MARKET_URL = "https://app.morpho.org/market"
PROTOCOL = "MORPHO"
BAD_DEBT_RATIO = 0.1

# Map vaults by chain
VAULTS_BY_CHAIN = {
    Chain.MAINNET: [
        ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"],
        ["Steakhouse USDT", "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa"],
        # ["Usual Boosted USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D"],
        ["Gantlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618"],
        ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d"],
        ["Gauntlet USDT Prime", "0x8CB3649114051cA5119141a34C200D65dc0Faa73"],
        ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658"],
        ["Gantlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458"],
        ["Gantlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5"],
        ["Gantlet WBTC Core", "0x443df5eEE3196e9b2Dd77CaBd3eA76C3dee8f9b2"],
        ["LlamaRisk crvUSD Vault", "0x67315dd969B8Cd3a3520C245837Bf71f54579C75"],
    ],
    Chain.BASE: [
        ["Moonwell Flagship USDC", "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca"],
        ["Moonwell Flagship ETH", "0xa0E430870c4604CcfC7B38Ca7845B1FF653D0ff1"],
        ["Moonwell Flagship EURC", "0xf24608E0CCb972b0b0f4A6446a0BBf58c701a026"],
    ],
}


def bad_debt_alert(markets):
    for market in markets:
        bad_debt = market["badDebt"]["usd"]
        borrowed_tvl = market["state"]["borrowAssetsUsd"]
        if borrowed_tvl == 0:
            continue
        if bad_debt / borrowed_tvl > BAD_DEBT_RATIO:
            chain_id = market["collateralAsset"]["chain"]["id"]
            chain_name = Chain.from_chain_id(chain_id).network_name
            market_url = f"{MARKET_URL}?id={market['uniqueKey']}&network={chain_name}"
            message = f"Bad debt for Morpho {market['uniqueKey']} is {market['badDebt']['usd']} USD. See more info about market: {market_url}\n"
            send_telegram_message(message, PROTOCOL)


def get_markets_from_vaults():
    query = """
    query GetVaults($addresses: [String!]!) {
        vaults(where: { address_in: $addresses } ) {
            items {
                address
                name
                state {
                    allocation {
                        market {
                            id
                            uniqueKey
                            loanAsset {
                                address
                                symbol
                            }
                            collateralAsset {
                                address
                                symbol
                                chain {
                                    id
                                }
                            }
                            state {
                                utilization
                                borrowAssetsUsd
                                supplyAssetsUsd
                            }
                            badDebt {
                                underlying
                                usd
                            }
                        }
                    }
                }
            }
        }
    }
    """

    # Collect all vault addresses from all chains
    vault_addresses = []
    for chain, vaults in VAULTS_BY_CHAIN.items():
        vault_addresses.extend([vault[1] for vault in vaults])

    json_data = {"query": query, "variables": {"addresses": vault_addresses}}

    response = requests.post(API_URL, json=json_data)

    if response.status_code != 200:
        print(f"Error: API request failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return []

    response_data = response.json()
    if "errors" in response_data:
        print(f"GraphQL Errors: {response_data['errors']}")
        return []

    vaults_data = response_data.get("data", {}).get("vaults", {}).get("items", [])
    all_markets = []

    # append all markets from each vault
    for vault_data in vaults_data:
        vault_markets = vault_data.get("state", {}).get("allocation", [])
        print(f"Vault: {vault_data['name']} has {len(vault_markets)} markets")

        # Check for markets with bad debt
        for allocation in vault_markets:
            market = allocation["market"]
            all_markets.append(market)

    return all_markets


def main():
    all_markets = get_markets_from_vaults()
    if len(all_markets) == 0:
        send_telegram_message(
            "🚨 Problem with fetching bad debt data for Morpho markets 🚨", PROTOCOL
        )

    bad_debt_alert(all_markets)


if __name__ == "__main__":
    main()
