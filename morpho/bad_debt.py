import requests
from utils.telegram import send_telegram_message


API_URL = "https://blue-api.morpho.org/graphql"
MARKET_URL = "https://app.morpho.org/market"
PROTOCOL = "TEST"  # TODO: add env values for telegram for protocol MORPHO
BAD_DEBT_RATIO = 0.1


def get_morpho_markets():
    variables = {
        "wanted_markets": [
            # Mainnet Vaults defined in morpho/main.py
            # DAI
            "0xe37784e5ff9c2795395c5a41a0cb7ae1da4a93d67bfdd8654b9ff86b3065941c",  # PT-sUSDE-26DEC2024 / DAI
            "0x5e3e6b1e01c5708055548d82d01db741e37d03b948a7ef9f3d4b962648bcbfa7",  # PT-sUSDE-27MAR2025 / DAI
            "0x8e6aeb10c401de3279ac79b4b2ea15fc94b7d9cfc098d6c2a1ff7b2b26d9d02c",  # USDe / DAI
            "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",  # sUSDe / DAI
            # USDC
            "0xb48bb53f0f2690c71e8813f2dc7ed6fca9ac4b0ace3faa37b4a8e5ece38fa1a2",  # USD0++ / USDC
            "0x8411eeb07c8e32de0b3784b6b967346a45593bfd8baeb291cc209dc195c7b3ad",  # PT-USD0++-27MAR2025 / USDC
            "0x864c9b82eb066ae2c038ba763dfc0221001e62fc40925530056349633eb0a259",  # USD0USD0++ / USDC
            "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc",  # wstETH / USDC
            "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49",  # WBTC / USDC
            "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64",  # cbBTC / USDC
            "0x346afa2b6d528222a2f9721ded6e7e2c40ac94877a598f5dae5013c651d2a462",  # PT-sUSDE-27MAR2025 / USDC
            "0x85c7f4374f3a403b36d54cc284983b2b02bbd8581ee0f3c36494447b87d9fcab",  # sUSDe / USDC
            "0xe4cfbee9af4ad713b41bf79f009ca02b17c001a0c0e7bd2e6a89b1111b3d3f08",  # tBTC / USDC
            "0x97bb820669a19ba5fa6de964a466292edd67957849f9631eb8b830c382f58b7f",  # MKR / USDC
            "0x7e9c708876fa3816c46aeb08937b51aa0461c2af3865ecb306433db8a80b1d1b",  # pufETH / USDC
            "0xd925961ad5df1d12f677ff14cf20bac37ea5ef3b325d64d5a9f4c0cc013a1d47",  # stUSD / USDC
            "0x61765602144e91e5ac9f9e98b8584eae308f9951596fd7f5e0f59f21cd2bf664",  # weETH / USDC
            # WETH
            "0x138eec0e4a1937eb92ebc70043ed539661dd7ed5a89fb92a720b341650288a40",  # WBTC / WETH
            "0xd0e50cdac92fe2172043f5e0c36532c6369d24947e40968f34a5e8819ca9ec5d",  # wstETH / WETH
            "0xc54d7acf14de29e0e5527cabd7a576506870346a78a11a6762e2cca66322ec41",  # wsETH / WETH
            "0x3c83f77bde9541f8d3d82533b19bbc1f97eb2f1098bb991728acbfbede09cc5d",  # rETH / WETH
            "0x37e7484d642d90f14451f1910ba4b7b8e4c3ccdd0ec28f8b2bdb35479e472ba7",  # weETH / WETH
            "0xa0534c78620867b7c8706e3b6df9e69a2bc67c783281b7a77e034ed75cee012e",  # ezETH / WETH
            "0x0eed5a89c7d397d02fd0b9b8e42811ca67e50ed5aeaa4f22e506516c716cfbbf",  # pufETH / WETH
            "0xcacd4c39af872ddecd48b650557ff5bcc7d3338194c0f5b2038e0d4dec5dc022",  # rswETH / WETH
            "0xba761af4134efb0855adfba638945f454f0a704af11fc93439e20c7c5ebab942",  # rsETH / WETH
            "0x5f8a138ba332398a9116910f4d5e5dcd9b207024c5290ce5bc87bc2dbd8e4a86",  # ETH+ / WETH
            "0xd5211d0e3f4a30d5c98653d988585792bb7812221f04801be73a44ceecb11e89",  # osETH / WETH
            "0x2287407f0f42ad5ad224f70e4d9da37f02770f79959df703d6cfee8afc548e0d",  # STONE / WETH
            "0xb7ad412532006bf876534ccae59900ddd9d1d1e394959065cb39b12b22f94ff5",  # agETH / WETH
            "0x49bb2d114be9041a787432952927f6f144f05ad3e83196a7d062f374ee11d0ee",  # ezETH / WETH
            # Base Vaults defined in morpho/main.py
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
        borrowed_tvl = market["state"]["borrowAssetsUsd"]
        bad_debt = market["badDebt"]["usd"]
        if bad_debt / borrowed_tvl > BAD_DEBT_RATIO:
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
