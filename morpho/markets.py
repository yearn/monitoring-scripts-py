import requests
from utils.telegram import send_telegram_message
from utils.chains import Chain


API_URL = "https://blue-api.morpho.org/graphql"
MORPHO_URL = "https://app.morpho.org"
PROTOCOL = "MORPHO"
BAD_DEBT_RATIO = 0.005  # 0.5% of total borrowed tvl
LIQUIDITY_THRESHOLD = 0.01  # 1% of total assets

# Map vaults by chain
VAULTS_BY_CHAIN = {
    Chain.MAINNET: [
        # name, address, risk level
        ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB", 1],
        ["Steakhouse USDT", "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa", 1],
        ["Gantlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618", 1],
        ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d", 1],
        ["Gauntlet USDT Prime", "0x8CB3649114051cA5119141a34C200D65dc0Faa73", 1],
        ["Gantlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5", 2],
        ["LlamaRisk crvUSD Vault", "0x67315dd969B8Cd3a3520C245837Bf71f54579C75", 2],
        # these vaults are not used by yVaults
        ["Gantlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458", 3],
        ["Gantlet WBTC Core", "0x443df5eEE3196e9b2Dd77CaBd3eA76C3dee8f9b2", 3],
        ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658", 4],
        ["Usual Boosted USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D", 5],
    ],
    Chain.BASE: [
        ["Moonwell Flagship USDC", "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca", 2],
        ["Moonwell Flagship ETH", "0xa0E430870c4604CcfC7B38Ca7845B1FF653D0ff1", 2],
        ["Moonwell Flagship EURC", "0xf24608E0CCb972b0b0f4A6446a0BBf58c701a026", 2],
        [
            "Moonwell Frontier cbBTC",
            "0x543257eF2161176D7C8cD90BA65C2d4CaEF5a796",
            3,
        ],
    ],
}

MARKETS_RISK_1 = {
    Chain.MAINNET: [
        "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49",  # WBTC/USDC -> lltv 86%, oracle: chainlink
        "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc",  # wstETH/USDC -> lltv 86%, oracle: compound oracle wstETH/ETH, chainlink ETH/USD
        "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64",  # cbBTC/USDC -> lltv 86%, oracle: chainlink BTC/USD
        "0xb8fc70e82bc5bb53e773626fcc6a23f7eefa036918d7ef216ecfb1950a94a85e",  # wstETH/WETH -> lltv 96.5%, oracle: lido exchange rate
        "0xc54d7acf14de29e0e5527cabd7a576506870346a78a11a6762e2cca66322ec41",  # wstETH/WETH more aggressive on high utilization -> lltv 94.5%, oracle: compound oracle, uses
        "0xd0e50cdac92fe2172043f5e0c36532c6369d24947e40968f34a5e8819ca9ec5d",  # wstETH/WETH less aggressive on high utilization -> lltv 94.5%, oracle: lido exchange rate
        "0x138eec0e4a1937eb92ebc70043ed539661dd7ed5a89fb92a720b341650288a40",  # WBTC/WETH -> lltv 91.5%, oracle: chainlink BTC/ETH
        "0x2cbfb38723a8d9a2ad1607015591a78cfe3a5949561b39bde42c242b22874ec0",  # cbBTC/WETH -> lltv 91.5%, oracle: chainlink BTC/USD and chainlink ETH/USD
        "0x1929f8139224cb7d5db8c270addc9ce366d37ad279e1135f73c0adce74b0f936",  # sDAI/WETH -> lltv 86%, oracle: chainlink DAI/ETH
        "0x46981f15ab56d2fdff819d9c2b9c33ed9ce8086e0cce70939175ac7e55377c7f",  # sDAI/USDC -> lltv 96.5%, oracle: sDAI vault
        "0xa921ef34e2fc7a27ccc50ae7e4b154e16c9799d3387076c421423ef52ac4df99",  # WBTC/USDT -> lltv 86%, oracle: chainlink WBTC/BTC, chainlink BTC/USD and chainlink USDT/USD
        "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",  # sUSDS/USDT -> lltv 96.5%, oracle: chainlink USDT/USD, chainlink DAI/USD and sUSDS vault
        "0xe7e9694b754c4d4f7e21faf7223f6fa71abaeb10296a4c43a54a7977149687d2",  # wstETH/USDT -> lltv 86%, oracle: compound oracle wstETH/ETH, chainlink ETH/USDT
        "0x1ca7ff6b26581fe3155f391f3960d32a033b5f7d537b1f1932b2021a6cf4f706",  # sDAI/USDT -> lltv 94.5%, oracle: sDAI vault, chainlink DAI/USD and chainlink USDT/USD
    ],
    Chain.BASE: [
        "0x7fc498ddcb7707d6f85f6dc81f61edb6dc8d7f1b47a83b55808904790564929a",  # cbETH/EURC
        "0xa9b5142fa687a24c275faf731f13b52faa9873252bb4e1cb6077aa1f412edb0b",  # WETH/EURC
        "0x67ebd84b2fb39e3bc5a13d97e4c07abe1ea617e40654826e9abce252e95f049e",  # cbBTC/EURC
        "0xf7e40290f8ca1d5848b3c129502599aa0f0602eb5f5235218797a34242719561",  # wstETH/EURC
        "0x0103cbcd14c690f68a91ec7c84607153311e9954c94ac6eac06c9462db3fabb6",  # rETH/EURC
        "0x8793cf302b8ffd655ab97bd1c695dbd967807e8367a65cb2f4edaf1380ba1bda",  # WETH/USDC
        "0x9103c3b4e834476c9a62ea009ba2c884ee42e94e6e314a26f04d312434191836",  # cbBTC/USDC
        "0x13c42741a359ac4a8aa8287d2be109dcf28344484f91185f9a79bd5a805a55ae",  # wstETH/USDC
        "0x1c21c59df9db44bf6f645d854ee710a8ca17b479451447e9f56758aee10a2fad",  # cbETH/USDC
        "0xdb0bc9f10a174f29a345c5f30a719933f71ccea7a2a75a632a281929bba1b535",  # rETH/USDC
        "0x3a4048c64ba1b375330d376b1ce40e4047d03b47ab4d48af484edec9fec801ba",  # wstETH/WETH -> lltv 94.5%, oracle: Chainlink wstETH-stETH Exchange Rate
        "0x84662b4f95b85d6b082b68d32cf71bb565b3f22f216a65509cc2ede7dccdfe8c",  # cbETH/WETH -> lltv 94.5%, oracle: Chainlink cbETH-ETH Exchange Rate
        "0x5dffffc7d75dc5abfa8dbe6fad9cbdadf6680cbe1428bafe661497520c84a94c",  # cbBTC/WETH -> lltv 91.5%, oracle: Chainlink BTC/USD and Chainlink ETH/USD
    ],
}

MARKETS_RISK_2 = {
    Chain.MAINNET: [
        "0x85c7f4374f3a403b36d54cc284983b2b02bbd8581ee0f3c36494447b87d9fcab",  # sUSDe/USDC -> lltv 91.5%, oracle: sUSDe vault
        "0xf6a056627a51e511ec7f48332421432ea6971fc148d8f3c451e14ea108026549",  # LBTC/WBTC -> lltv 94.5%, oracle: readstone exchange rate LBTC/BTC and chainlink WBTC/BTC
        "0x346afa2b6d528222a2f9721ded6e7e2c40ac94877a598f5dae5013c651d2a462",  # PT-sUSDE-27MAR2025 / USDC, lltv 91.5%, oracle: Pendle PT with LinearDiscountOracle, aggresive interest rate on high utilization
        "0x27852bb453d4fe6ec918dd27b7136bb233d210aab1758a59ed8daaeec24f7b3d",  # PT-sUSDE-27FEB2025 / USDC, lltv 91.5%, oracle: Pendle PT with LinearDiscountOracle, aggresive interest rate on high utilization
        "0x5e3e6b1e01c5708055548d82d01db741e37d03b948a7ef9f3d4b962648bcbfa7",  # PT-sUSDE-27MAR2025 / DAI -> lltv 91.5%, using aggresive interest rate curve and using discounted oracle
        "0xab0dcab71e65c05b7f241ea79a33452c87e62db387129e4abe15e458d433e4d8",  # PT-USDe-27MAR2025 / DAI -> lltv 91.5%, using aggresive interest rate curve and using discounted oracle
        "0x74ef8d7022b0ef0c0e6dc001fbda3c8bd9a3e706f03bb559c833e1dce7302d3a",  # Curve TricryptoUSDC LP / crvUSD -> lltv 86%, collaterals: ETH, USDC, WBTC
        "0x1c4b9ce834604969d33dc277bd8473d8aee856e5a577c08427b6deeb97cc72d6",  # Curve TricryptoUSDT LP / crvUSD -> lltv 86%, collaterals: ETH, USDT, WBTC
        "0x42e157d3739f9ae3f418f5dd0977b7d51c3a677502afd9f3f594f46cc07dec6a",  # Curve TryLSD LP / crvUSD -> lltv 86%, collaterals: wstETH, rETH, sfrxETH
        "0xbd2a27358bdaf3fb902a0ad17f86d4633f9ac5377941298720b37a4d90deab96",  # Curve TriCRV LP / crvUSD -> lltv 86%, collaterals: crvUSD, ETH, crv
    ],
    Chain.BASE: [],
}

MARKETS_RISK_3 = {
    Chain.MAINNET: [
        "0x0cd36e6ecd9d846cffd921d011d2507bc4c2c421929cec65205b3cd72925367c",  # Curve TricryptoLLAMA LP / crvUSD -> collaterals: crvUSD, wstETH, tBTC.
        "0x198132864e7974fb451dfebeb098b3b7e7e65566667fb1cf1116db4fb2ad23f9",  # PT-LBTC-27MAR2025 / WBTC, lltv 86%, oracle: Pendle PT exchange rate, readstone exchange rate LBTC/BTC and chainlink WBTC/BTC.
        "0xba761af4134efb0855adfba638945f454f0a704af11fc93439e20c7c5ebab942",  # rsETH/WETH -> lltv 94.5%, oracle: origami rsETH/ETH which calls KELP_LRT_ORACLE.rsETHPrice(). Oracle address: https://etherscan.io/address/0x349A73444b1a310BAe67ef67973022020d70020d
        "0xa0534c78620867b7c8706e3b6df9e69a2bc67c783281b7a77e034ed75cee012e",  # ezETH/WETH -> lltv 94.5%, oracle: origami ezETH/ETH which calls renzoOracle()).calculateRedeemAmount(). It is hypothetical price, not the actual price.
        "0x37e7484d642d90f14451f1910ba4b7b8e4c3ccdd0ec28f8b2bdb35479e472ba7",  # weETH/WETH -> lltv 94.5%, oracle: origami weETH/ETH which calls WEETH.getRate().
        "0x8e7cc042d739a365c43d0a52d5f24160fa7ae9b7e7c9a479bd02a56041d4cf77",  # USR/USDC
        "0x97bb820669a19ba5fa6de964a466292edd67957849f9631eb8b830c382f58b7f",  # MKR/USDC
        "0x718af3af39b183758849486340b69466e3e89b84b7884188323416621ee91cb7",  # UNI/USDC
        "0xe4cfbee9af4ad713b41bf79f009ca02b17c001a0c0e7bd2e6a89b1111b3d3f08",  # tBTC/USDC
        "0xd925961ad5df1d12f677ff14cf20bac37ea5ef3b325d64d5a9f4c0cc013a1d47",  # stUSDC/USDC
        "0x61765602144e91e5ac9f9e98b8584eae308f9951596fd7f5e0f59f21cd2bf664",  # weETH/USDC
        "0x9c765f69d8a8e40d2174824bc5107d05d7f0d0f81181048c9403262aeb1ab457",  # LINK/USDC
        "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",  # sUSDe / DAI -> same asset but using hardcoded oracle
        "0x8e6aeb10c401de3279ac79b4b2ea15fc94b7d9cfc098d6c2a1ff7b2b26d9d02c",  # USDe / DAI -> same asset but using hardcoded oracle
    ],
    Chain.BASE: [
        "0x9a697eb760dd12aaea23699c96ea2ebbfe48b7af64138d92c4d232b9ed380024",  # PT-LBTC-29MAY2025/cbBTC -> lltv 91.5%, oracle: Pendle PT with LinearDiscountOracle. Higher lltv than PT-LBTC-27MAR2025 / WBTC.
        "0x4944a1169bc07b441473b830308ffe5bb535c10a9f824e33988b60738120c48e",  # LBTC/cbBTC -> lltv 91.5%, oracle: Custom moonwell oracle. Base feed is fetched from upgradeable oracle which uses 2 oracles. Primary oracle is redstone oracle, if the price changes more than 2% than it uses fallback oracle chainlink oracle. Chainlink didn't have an exchange rate feed. Redstone was the only provider for the LBTC reserves.
    ],
}

MARKETS_RISK_4 = {
    Chain.MAINNET: [
        "0x3c83f77bde9541f8d3d82533b19bbc1f97eb2f1098bb991728acbfbede09cc5d",  # rETH/WETH -> lltv 94.5%, oracle: gravita rETH/ETH. Can change owner and aggregator.
        "0xe95187ba4e7668ab4434bbb17d1dfd7b87e878242eee3e73dac9fdb79a4d0d99",  # EIGEN/USDC
        "0x444327b909aa41043cc4f20209eefb2fbb37f1c38ff9ca312374a4ecc3f0a871",  # solvBTC/USDC
        "0x2287407f0f42ad5ad224f70e4d9da37f02770f79959df703d6cfee8afc548e0d",  # STONE/WETH -> centralization risk
        "0xf78b7d3a62437f78097745a5e3117a50c56a02ec5f072cba8d988a129c6d4fb6",  # beraSTONE/WETH -> centralization risk
        "0x5f8a138ba332398a9116910f4d5e5dcd9b207024c5290ce5bc87bc2dbd8e4a86",  # ETH+/WETH -> unknown asset
        "0xcacd4c39af872ddecd48b650557ff5bcc7d3338194c0f5b2038e0d4dec5dc022",  # rswETH/WETH -> unknown asset
        "0x0eed5a89c7d397d02fd0b9b8e42811ca67e50ed5aeaa4f22e506516c716cfbbf",  # pufETH/WETH -> check pufETH liquidity before moving up
        "0x7e9c708876fa3816c46aeb08937b51aa0461c2af3865ecb306433db8a80b1d1b",  # pufETH/USDC
        "0x514efda728a646dcafe4fdc9afe4ea214709e110ac1b2b78185ae00c1782cc82",  # swBTC/WBTC -> same asset, check swBTC liquidity before moving up
        "0x20c488469064c8e2f892dab33e8c7a631260817f0db57f7425d4ef1d126efccb",  # Re7wstETH/WETH -> unknown asset
    ],
    Chain.BASE: [],
}

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


def get_market_allocation_threshold(market_risk_level, vault_risk_level):
    """
    Get allocation threshold based on market and vault risk levels.
    For higher vault risk levels, thresholds shift up (become more permissive).
    For example, if vault risk level is 2, then market risk level 1 is 0.80, market risk level 2 is 0.30, etc.
    """
    # Shift market risk level down based on vault risk level
    adjusted_risk = max(1, market_risk_level - (vault_risk_level - 1))
    return ALLOCATION_TIERS[adjusted_risk]


def get_chain_name(chain: Chain):
    if chain == Chain.MAINNET:
        return "ethereum"
    else:
        return chain.name.lower()


def get_market_url(market):
    chain_id = market["collateralAsset"]["chain"]["id"]
    chain = Chain.from_chain_id(chain_id)
    return f"{MORPHO_URL}/{get_chain_name(chain)}/market/{market['uniqueKey']}"


def get_vault_url(vault_data):
    chain_id = vault_data["chain"]["id"]
    chain = Chain.from_chain_id(chain_id)
    return f"{MORPHO_URL}/{get_chain_name(chain)}/vault/{vault_data['address']}"


def bad_debt_alert(markets, vault_name=""):
    """
    Send telegram message if bad debt is detected in any market.
    """
    for market in markets:
        bad_debt = market["badDebt"]["usd"]
        borrowed_tvl = market["state"]["borrowAssetsUsd"]
        if borrowed_tvl == 0:
            continue
        if bad_debt / borrowed_tvl > BAD_DEBT_RATIO:
            market_url = get_market_url(market)
            message = f"Bad debt for Morpho {vault_name} - [{market['uniqueKey']}]({market_url}) is {market['badDebt']['usd']} USD\n"
            send_telegram_message(message, PROTOCOL)


def check_high_allocation(vault_data):
    """
    Send telegram message if high allocation is detected in any market.
    Send another message if total risk level is too high.
    """
    total_assets = vault_data["state"]["totalAssetsUsd"]
    if total_assets == 0:
        return

    vault_name = vault_data["name"]
    vault_url = get_vault_url(vault_data)
    chain = Chain.from_chain_id(vault_data["chain"]["id"])
    # Find vault in VAULTS_BY_CHAIN to get risk level
    vault_address = vault_data["address"]
    risk_level = None
    for vault in VAULTS_BY_CHAIN[chain]:
        if vault[1].lower() == vault_address.lower():
            risk_level = vault[2]
            break

    if risk_level is None:
        # Throw error if vault not found in config
        raise ValueError(f"Vault {vault_address} not found in VAULTS_BY_CHAIN config")

    total_risk_level = 0.0

    for allocation in vault_data["state"]["allocation"]:
        # market without collateral asset is idle asset
        if not allocation["enabled"] or allocation["market"]["collateralAsset"] is None:
            continue

        market = allocation["market"]
        unique_key = market["uniqueKey"]
        market_supply = allocation["supplyAssetsUsd"]
        allocation_ratio = market_supply / total_assets

        # Determine market risk level
        if unique_key in MARKETS_RISK_1[chain]:
            market_risk_level = 1
        elif unique_key in MARKETS_RISK_2[chain]:
            market_risk_level = 2
        elif unique_key in MARKETS_RISK_3[chain]:
            market_risk_level = 3
        elif unique_key in MARKETS_RISK_4[chain]:
            market_risk_level = 4
        else:
            market_risk_level = 5

        allocation_threshold = get_market_allocation_threshold(
            market_risk_level, risk_level
        )
        risk_multiplier = market_risk_level

        if allocation_ratio > allocation_threshold:
            market_url = get_market_url(market)
            market_name = (
                f"{market['collateralAsset']['symbol']}/{market['loanAsset']['symbol']}"
            )
            message = (
                f"🔺 High allocation detected in [{vault_name}]({vault_url})\n"
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
    print(f"Total risk level: {total_risk_level:.1%}, vault: {vault_name}")
    if total_risk_level > MAX_RISK_THRESHOLDS[risk_level]:
        message = (
            f"🔺 High allocation detected in [{vault_name}]({vault_url})\n"
            f"🔢 Total risk level: {total_risk_level:.1%} but max acceptable is {MAX_RISK_THRESHOLDS[risk_level]}\n"
            f"🔢 Total assets: ${total_assets:,.2f}\n"
        )
        send_telegram_message(message, PROTOCOL)


def check_low_liquidity(vault_data):
    """
    Send telegram message if low liquidity is detected.
    """
    vault_name = vault_data["name"]
    vault_url = get_vault_url(vault_data)
    total_assets = vault_data["state"]["totalAssetsUsd"]
    liquidity = vault_data["liquidity"]["usd"]

    if total_assets == 0:
        return

    liquidity_ratio = liquidity / total_assets
    if liquidity_ratio < LIQUIDITY_THRESHOLD:
        message = (
            f"⚠️ Low liquidity detected in [{vault_name}]({vault_url})\n"
            f"💰 Liquidity: {liquidity_ratio:.1%} of total assets\n"
            f"💵 Liquidity: ${liquidity:,.2f}\n"
            f"📊 Total Assets: ${total_assets:,.2f}"
        )
        send_telegram_message(message, PROTOCOL)


def main():
    """
    Check markets for low liquidity, high allocation and bad debt.
    Send telegram message if data cannot be fetched.
    """
    # Collect all vault addresses from all chains
    vault_addresses = []
    for chain, vaults in VAULTS_BY_CHAIN.items():
        vault_addresses.extend([vault[1] for vault in vaults])

    query = """
    query GetVaults($addresses: [String!]!) {
        vaults(where: { address_in: $addresses } ) {
            items {
                address
                name
                chain {
                  id
                }
                liquidity {
                  usd
                }
                state {
                    totalAssetsUsd
                    allocation {
                        enabled
                        supplyAssetsUsd
                        pendingSupplyCapUsd
                        pendingSupplyCapValidAt
                        market {
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

    json_data = {"query": query, "variables": {"addresses": vault_addresses}}

    response = requests.post(API_URL, json=json_data)

    if response.status_code != 200:
        send_telegram_message(
            "🚨 Problem with fetching data for Morpho markets 🚨", PROTOCOL
        )
        return

    vaults_data = response.json().get("data", {}).get("vaults", {}).get("items", [])
    if len(vaults_data) == 0:
        send_telegram_message("🚨 No vaults data found 🚨", PROTOCOL)
        return

    for vault_data in vaults_data:
        # Check liquidity
        check_low_liquidity(vault_data)

        # Check high allocation for each vault
        check_high_allocation(vault_data)

        # Check bad debt for each market in the vault
        vault_markets = []
        for allocation in vault_data["state"]["allocation"]:
            if (
                allocation["enabled"]
                and allocation.get("market", {})
                .get("state", {})
                .get("supplyAssetsUsd", 0)
                > 0
            ):
                market = allocation["market"]
                if market["collateralAsset"] is not None:
                    # market without collateral asset is idle asset
                    vault_markets.append(market)

        bad_debt_alert(vault_markets, vault_data["name"])


if __name__ == "__main__":
    main()
