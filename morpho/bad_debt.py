import requests
from utils.telegram import send_telegram_message


API_URL = "https://blue-api.morpho.org/graphql"
MARKET_URL = "https://app.morpho.org/market"
PROTOCOL = "MORPH"  # TODO: add env values for telegram for protocol MORPHO


def get_morpho_markets():
    variables = {
        "wanted_markets": [
            # Mainnet: Usual boosted + Steakhouse
            "0xb48bb53f0f2690c71e8813f2dc7ed6fca9ac4b0ace3faa37b4a8e5ece38fa1a2",  # USD0++ / USDC
            "0x8411eeb07c8e32de0b3784b6b967346a45593bfd8baeb291cc209dc195c7b3ad",  # PT-USD0++-27MAR2025 / USDC
            "0x864c9b82eb066ae2c038ba763dfc0221001e62fc40925530056349633eb0a259",  # USD0USD0++ / USDC
            "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc",  # wstETH / USDC
            "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49",  # WBTC / USDC
            "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64",  # cbBTC / USDC
            # Base: Moonwell Flagship USDC
            "0x1c21c59df9db44bf6f645d854ee710a8ca17b479451447e9f56758aee10a2fad",  # cbETH / USDC
            "0x13c42741a359ac4a8aa8287d2be109dcf28344484f91185f9a79bd5a805a55ae",  # wstETH / USDC
            "0x9103c3b4e834476c9a62ea009ba2c884ee42e94e6e314a26f04d312434191836",  # cbBTC / USDC
            "0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda",  # WETH / USDC
        ],
    }

    query_bad_debt = """
    query($wanted_markets: [String!]!) {
    markets(where: {uniqueKey_in: $wanted_markets}) {
        items {
        uniqueKey
        loanAsset {
            address
        }
        collateralAsset {
            address
            chain {
            id
            }
        }
        state {
            utilization
        }
        badDebt {
            underlying
            usd
        }
        }
    }
    }
    """

    json_data = {
        "query": query_bad_debt,
        "variables": variables,
    }
    response = requests.post(
        API_URL,
        json=json_data,
    )
    return response.json()["data"]["markets"]["items"]


def bad_debt_alert(markets):
    for market in markets:
        if market["badDebt"]["usd"] > 0:
            chainId = market["collateralAsset"]["chain"]["id"]
            if chainId == 1:
                market_name = "mainnet"
            elif chainId == 8453:
                market_name = "base"
            else:
                market_name = "unknown"

            market_url = f"{MARKET_URL}?id={market['uniqueKey']}&network={market_name}"
            message = f"Bad debt for Morpho {market['uniqueKey']} is {market['badDebt']['usd']} USD. See more info about market: {market_url}\n"
            send_telegram_message(message, PROTOCOL)


def main():
    markets = get_morpho_markets()
    bad_debt_alert(markets)


if __name__ == "__main__":
    main()
