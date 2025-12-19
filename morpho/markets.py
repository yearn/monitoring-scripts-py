"""
Morpho markets monitoring script.

This module checks Morpho markets for:
1. Bad debt
2. High allocation levels
3. Low liquidity
"""

from typing import Any, Dict, List

import requests

from utils.chains import Chain
from utils.telegram import send_telegram_message

# Configuration constants
API_URL = "https://api.morpho.org/graphql"
MORPHO_URL = "https://app.morpho.org"
PROTOCOL = "MORPHO"
BAD_DEBT_RATIO = 0.005  # 0.5% of total borrowed tvl
LIQUIDITY_THRESHOLD = 0.01  # 1% of total assets
LIQUIDITY_THRESHOLD_YV_COLLATERAL = 0.15  # 15% of total assets

# Map vaults by chain
VAULTS_BY_CHAIN = {
    Chain.MAINNET: [
        # name, address, risk level
        ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB", 1],
        ["Steakhouse USDT", "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa", 3],
        ["Gauntlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618", 1],
        ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d", 1],
        ["Gauntlet USDT Prime", "0x8CB3649114051cA5119141a34C200D65dc0Faa73", 1],
        ["Gauntlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5", 2],
        ["LlamaRisk crvUSD Vault", "0x67315dd969B8Cd3a3520C245837Bf71f54579C75", 2],
        ["Yearn OG WETH", "0xE89371eAaAC6D46d4C3ED23453241987916224FC", 2],
        ["Yearn OG USDC", "0xF9bdDd4A9b3A45f980e11fDDE96e16364dDBEc49", 2],
        ["Yearn Degen USDC", "0xdC2Dd5189F70Fe2832D9caf7b17d27AA3D79dbE1", 3],
        # these vaults are not used by yVaults
        ["Gauntlet WBTC Core", "0x443df5eEE3196e9b2Dd77CaBd3eA76C3dee8f9b2", 3],
        ["Gauntlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458", 4],
        ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658", 4],
        ["MEV Capital USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D", 5],
        # Vault Bridge for Katana Chain
        ["Vault Bridge USDC", "0xBEefb9f61CC44895d8AEc381373555a64191A9c4", 1],
        ["Vault Bridge USDT", "0xc54b4E08C1Dcc199fdd35c6b5Ab589ffD3428a8d", 1],
        ["Vault Bridge WETH", "0x31A5684983EeE865d943A696AAC155363bA024f9", 1],
        ["Vault Bridge WBTC", "0x812B2C6Ab3f4471c0E43D4BB61098a9211017427", 2],
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
        ["Seamless/Gauntlet USDC", "0x616a4E1db48e22028f6bbf20444Cd3b8e3273738", 3],
        ["Seamless/Gauntlet WETH", "0x27D8c7273fd3fcC6956a0B370cE5Fd4A7fc65c18", 3],
        ["Seamless/Gauntlet cbBTC", "0x5a47C803488FE2BB0A0EAaf346b420e4dF22F3C7", 3],
        ["Yearn OG WETH", "0x1D795E29044A62Da42D927c4b179269139A28A6B", 2],
        ["Yearn OG USDC", "0xef417a2512C5a41f69AE4e021648b69a7CdE5D03", 2],
    ],
    Chain.KATANA: [
        ["Yearn OG WETH", "0xFaDe0C546f44e33C134c4036207B314AC643dc2E", 1],
        ["Yearn OG USDC", "0xCE2b8e464Fc7b5E58710C24b7e5EBFB6027f29D7", 1],
        ["Yearn OG USDT", "0x8ED68f91AfbE5871dCE31ae007a936ebE8511d47", 1],
        ["Yearn OG WBTC", "0xe107cCdeb8e20E499545C813f98Cc90619b29859", 1],
        ["Gauntlet USDC", "0xE4248e2105508FcBad3fe95691551d1AF14015f7", 2],
        # ["SteakhouseHigh Yield USDC", "0x1445A01a57D7B7663CfD7B4EE0a8Ec03B379aabD", 1],
        ["Gauntlet USDT", "0x1ecDC3F2B5E90bfB55fF45a7476FF98A8957388E", 1],
        ["SteakhousePrime USDC", "0x61D4F9D3797BA4dA152238c53a6f93Fb665C3c1d", 1],
        ["Gauntlet WETH", "0xC5e7AB07030305fc925175b25B93b285d40dCdFf", 1],
        ["Gauntlet WBTC", "0xf243523996ADbb273F0B237B53f30017C4364bBC", 1],
        ["SteakhousePrime AUSD", "0x82c4C641CCc38719ae1f0FBd16A64808d838fDfD", 1],
        ["Gauntlet AUSD", "0x9540441C503D763094921dbE4f13268E6d1d3B56", 1],
    ],
    Chain.POLYGON: [
        ["Compound WETH", "0xF5C81d25ee174d83f1FD202cA94AE6070d073cCF", 1],
        ["Compound USDC", "0x781FB7F6d845E3bE129289833b04d43Aa8558c42", 2],
        ["Compound USDT", "0xfD06859A671C21497a2EB8C5E3fEA48De924D6c8", 1],
    ],
}

# Morpho Vaults that are used by Yearn Strategies which are used as YV collateral in Morpho Markets
# Organized by asset address for easier grouping and management
VAULTS_WITH_YV_COLLATERAL_BY_ASSET = {
    Chain.MAINNET: {
        # USDC vaults
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": [
            ["OEV USDC", "0x68Aea7b82Df6CcdF76235D46445Ed83f85F845A3"],
            ["SteakhousePrime USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"],
            ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d"],
        ],
        # WETH vaults
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": [
            ["Gauntlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618"],
        ],
    },
    Chain.KATANA: {
        # USDC vaults - using addresses from VAULTS_BY_CHAIN as source of truth
        "0x203A662b0BD271A6ed5a60EdFbd04bFce608FD36": [  # USDC asset address on Katana
            ["Yearn OG USDC", "0xCE2b8e464Fc7b5E58710C24b7e5EBFB6027f29D7"],
            ["SteakhousePrime USDC", "0x61D4F9D3797BA4dA152238c53a6f93Fb665C3c1d"],
            ["SteakhouseHigh Yield USDC", "0x1445A01a57D7B7663CfD7B4EE0a8Ec03B379aabD"],
            ["Gauntlet USDC", "0xE4248e2105508FcBad3fe95691551d1AF14015f7"],
        ],
        # USDT vaults - using addresses from VAULTS_BY_CHAIN as source of truth
        "0x2DCa96907fde857dd3D816880A0df407eeB2D2F2": [  # USDT asset address on Katana
            [
                "Yearn OG USDT",
                "0x8ED68f91AfbE5871dCE31ae007a936ebE8511d47",
            ],  # Corrected from VAULTS_BY_CHAIN
            ["Gauntlet USDT", "0x1ecDC3F2B5E90bfB55fF45a7476FF98A8957388E"],
        ],
        # WETH vaults - using addresses from VAULTS_BY_CHAIN as source of truth
        "0xEE7D8BCFb72bC1880D0Cf19822eB0A2e6577aB62": [  # WETH asset address on Katana
            [
                "Gauntlet WETH",
                "0xC5e7AB07030305fc925175b25B93b285d40dCdFf",
            ],  # Corrected from VAULTS_BY_CHAIN
            ["Yearn OG WETH", "0xFaDe0C546f44e33C134c4036207B314AC643dc2E"],
        ],
        # WBTC vaults - using addresses from VAULTS_BY_CHAIN as source of truth
        "0x0913DA6Da4b42f538B445599b46Bb4622342Cf52": [  # WBTC asset address on Katana
            ["Yearn OG WBTC", "0xe107cCdeb8e20E499545C813f98Cc90619b29859"],
            ["Gauntlet WBTC", "0xf243523996ADbb273F0B237B53f30017C4364bBC"],
        ],
        # AUSD vaults - using addresses from VAULTS_BY_CHAIN as source of truth
        "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a": [  # AUSD asset address on Katana
            ["SteakhousePrime AUSD", "0x82c4C641CCc38719ae1f0FBd16A64808d838fDfD"],
            ["Gauntlet AUSD", "0x9540441C503D763094921dbE4f13268E6d1d3B56"],
        ],
    },
}


MARKETS_RISK_1 = {
    Chain.MAINNET: [
        "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49",  # WBTC/USDC -> lltv 86%, oracle: chainlink
        "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc",  # wstETH/USDC -> lltv 86%, oracle: compound oracle wstETH/ETH, chainlink ETH/USD
        "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64",  # cbBTC/USDC -> lltv 86%, oracle: chainlink BTC/USD
        "0xb8fc70e82bc5bb53e773626fcc6a23f7eefa036918d7ef216ecfb1950a94a85e",  # wstETH/WETH -> lltv 96.5%, oracle: lido exchange rate
        "0xc54d7acf14de29e0e5527cabd7a576506870346a78a11a6762e2cca66322ec41",  # wstETH/WETH -> lltv 94.5%, oracle: compound oracle, uses
        "0xd0e50cdac92fe2172043f5e0c36532c6369d24947e40968f34a5e8819ca9ec5d",  # wstETH/WETH -> lltv 94.5%, oracle: lido exchange rate
        "0x138eec0e4a1937eb92ebc70043ed539661dd7ed5a89fb92a720b341650288a40",  # WBTC/WETH -> lltv 91.5%, oracle: chainlink BTC/ETH
        "0x2cbfb38723a8d9a2ad1607015591a78cfe3a5949561b39bde42c242b22874ec0",  # cbBTC/WETH -> lltv 91.5%, oracle: chainlink BTC/USD and chainlink ETH/USD
        "0x1929f8139224cb7d5db8c270addc9ce366d37ad279e1135f73c0adce74b0f936",  # sDAI/WETH -> lltv 86%, oracle: chainlink DAI/ETH
        "0x46981f15ab56d2fdff819d9c2b9c33ed9ce8086e0cce70939175ac7e55377c7f",  # sDAI/USDC -> lltv 96.5%, oracle: sDAI vault
        "0xa921ef34e2fc7a27ccc50ae7e4b154e16c9799d3387076c421423ef52ac4df99",  # WBTC/USDT -> lltv 86%, oracle: chainlink WBTC/BTC, chainlink BTC/USD and chainlink USDT/USD
        "0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b",  # sUSDS/USDT -> lltv 96.5%, oracle: chainlink USDT/USD, chainlink DAI/USD and sUSDS vault
        "0xe7e9694b754c4d4f7e21faf7223f6fa71abaeb10296a4c43a54a7977149687d2",  # wstETH/USDT -> lltv 86%, oracle: compound oracle wstETH/ETH, chainlink ETH/USDT
        "0x1ca7ff6b26581fe3155f391f3960d32a033b5f7d537b1f1932b2021a6cf4f706",  # sDAI/USDT -> lltv 94.5%, oracle: sDAI vault, chainlink DAI/USD and chainlink USDT/USD
        "0xb1eac1c0f3ad13fb45b01beac8458c055c903b1bff8cb882346635996a774f77",  # sDAI / DAI -> lltv 98%, oracle is sDAI vault
        "0x37e7484d642d90f14451f1910ba4b7b8e4c3ccdd0ec28f8b2bdb35479e472ba7",  # weETH/WETH -> lltv 94.5%, oracle: origami weETH/ETH which calls WEETH.getRate(). Alike assets.
        "0x45671fb8d5dea1c4fbca0b8548ad742f6643300eeb8dbd34ad64a658b2b05bca",  # cbBTC/USDT -> lltv 86%, oracle: chainlink BTC/USD, hardcoded USDT=USD.
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
        "0xa7813c754ddd6a24e1a1a29ff3ea877803ac63d09efc2f121b1cf3f0bf3af2f6",  # WETH/cbBTC -> lltv 91.5%, oracle: Chainlink ETH/USD and Chainlink BTC/USD
        "0xdc69cf2caae7b7d1783fb5a9576dc875888afad17ab3d1a3fc102f741441c165",  # rETH/WETH -> lltv 94.5%, oracle: Chainlink rETH/ETH
        "0x78d11c03944e0dc298398f0545dc8195ad201a18b0388cb8058b1bcb89440971",  # weWETH/WETH -> lltv 91.5%, oracle: Chainlink weETH/ETH exchange rate
        "0x3b3769cfca57be2eaed03fcc5299c25691b77781a1e124e7a8d520eb9a7eabb5",  # USDC/WETH -> lltv 86.5%, oracle: Chainlink USDC/USD and Chainlink ETH/USD
    ],
    Chain.KATANA: [
        "0xcd2dc555dced7422a3144a4126286675449019366f83e9717be7c2deb3daae3e",  # vbWBTC/vbUSDC -> lltv 86%, oracle: Chainlink WBTC/BTC, Chainlink BTC/USD and Chainlink USDC/USD
        "0x2fb14719030835b8e0a39a1461b384ad6a9c8392550197a7c857cf9fcbd6c534",  # vbETH/vbUSDC -> lltv 86%, oracle: Chainlink ETH/USD and Chainlink USDC/USD
        "0x60b54e17d55b765955a20908ed5143192a48df7fd3833f7f7fe86504bf6c4c1a",  # LBTC/vbBTC -> lltv 91.5%,  oracle: RedStone Price Feed for LBTC_FUNDAMENTAL -> Katana WBTC vault bridge accepts LBTC markets as collateral, no additional risk when using LBTC on Katana chain
        "0xd3b3c992070b5a6271b11acde46cdad575e4187e499782e084d73e523153f1ed",  # wstETH/vbUSDC -> lltv 86%, oracle: Chainlink wsteth/ETH, Chainlink ETH/USD and Chainlink USDC/USD
        "0x4b7a328d4c03ea974acac4a4c5f092870afe707df88aa4c5d834f93d96894050",  # vbETH/vbUSDC -> lltv 86%, oracle: Api3 ETH/USD and Api3 USDC/USD
        "0x499a1b2827cff06de432a00b5e8c4509d4c2a7eafc638c0df6a09a8fa1c8d649",  # vbWBTC/vbUSDC -> lltv 86%, oracle: Api3 BTC/USD and Api3 USDC/USD
        "0x4bc9c84a5271f5196357c0ed18af783614851f23ac11652e78b9934e34baa5d1",  # vbETH/vbUSDT -> lltv 86%, oracle: Api3 ETH/USD and Api3 USDT/USD
        "0x9c95ce191559ba7652c7a2d74568590824c1166a2994fcef696b413c18efe7ee",  # vbWBTC/vbUSDT -> lltv 86%, oracle: Api3 BTC/USD and Api3 USDT/USD
        "0x1e74d36ffbda65b8a45d72754b349cdd5ce807c5fa814f91ba8e3cd27881c34b",  # weETH/vbETH -> lltv 91.5%, oracle: Redstone weETH/ETH fundamental price
        "0x22f9f76056c10ee3496dea6fefeaf2f98198ef597eda6f480c148c6d3aaa70db",  # wstETH/vbETH -> lltv 91.5%, oracle: Redstone wstETH/ETH fundamental price
        "0xc149387c455f7abf7a1f430ccc6639df55fcd366a2f5b055f611289ed1b8a956",  # LBTC/vbUSDT -> lltv 86%, oracle: Redstone LBTC/BTC fundamental price and Redstone BTC/USD
        "0xa0cd6b9d1fcc6baded4f7f8f93697dbe7f24f6e1fc22602a625c7a80b8e8e6ef",  # LBTC/vbUSDC -> lltv 86%, oracle: Chainlink LBTC/USD and Chainlink USDC/USD
        "0xcdaf57d98c2f75bffb8f0d3f7aa79bbacda4a479c47e316aab14af1ca6d85ffc",  # yvUSDT/vbUSDC -> lltv 86%, oracle: yvUSDT vault rate. Chainlink USDT/USD and Chainlink USDC/USD
        "0x6691cdcadd5d23ac68d2c1cf54dc97ab8242d2a888230de411094480252c2ed3",  # yvUSDC/vbUSDT -> lltv 86%, oracle: yvUSDC vault rate. Chainlink USDC/USD and Chainlink USDT/USD
        "0xd4ab732112fa9087c9c3c3566cd25bc78ee7be4f1b8bdfe20d6328debb818656",  # vbWBTC/vbUSDT -> lltv 86%, oracle: Chainlink WBTC/USD
        "0x9e03fc0dc3110daf28bc6bd23b32cb20b150a6da151856ead9540d491069db1c",  # vbETH/vbUSDT -> lltv 86%, oracle: Chainlink ETH/USD
        "0x08f67ef41398456dbc5ff72d43c8b6f7917abfd01498a9fc6c89dabe6eb78b8c",  # yvvbETH/USDC -> lltv 77%, oracle: yearn vault exchange rate. Chainlink ETH/USD and Chainlink USDC/USD.
        "0x3a22063bd258f3f75e3135cac4ec53435dfa5b47b3d5173bb8fd5278e6c1b305",  # yvvbWBTC/USDC -> lltv 77%, oracle: yearn vault exchange rate. Chainlink WBTC/BTC, Chainlink BTC/USD and Chainlink USDC/USD.
        "0xcfac40b9f06194a33d9526f73642f6849b908c2b6d8669ad9d2d4a3e7dcb017a",  # yvAUSD/USDC -> lltv 86%, oracle: yearn vault exchange rate. Chainlink AUSD/USD and Chainlink USDC/USD.
        "0xbeb2f6ad6de1a9eead3302ad57a0180f67d127a22e53fa29bc724147b96cb20d",  # WBTC/AUSD -> lltv 86%, oracle: Chainlink WBTC/BTC, Chainlink BTC/USD and Chainlink AUSD/USD.
        "0x02a77b251cb27b04b5ddab89c852bdc77ee85d359c082170389001d71571a967",  # vbWETH/AUSD -> lltv 86%, oracle: Chainlink ETH/USD and Chainlink AUSD/USD.
        "0x0c909f9c866c4250cb2f15ef916b1eed5b1022b34ccd7ca947810011f5758c4f",  # BTCK/AUSD -> lltv 86%, oracle: RedStone Price Feed for BTC. USD=AUSD.
        "0xa6ce59291d90ae348b2fa956cc66f31df605a3304a9325e494c94e2cf5b0485a",  # weETH/vbUSDT -> lltv 77%, oracle: RedStone weETH/ETH fundamental price, Chainlink ETH/USD and Chainlink USDT/USD.
        "0x76e311d4b0e2e6ae88ad9bab18063452a6d39837d7104c430ff62457b91cb2cb",  # weETH/vbUSDC -> lltv 77%, oracle: RedStone weETH/ETH fundamental price, Chainlink ETH/USD and Chainlink USDC/USD.
    ],
    Chain.POLYGON: [
        "0xb8ae474af3b91c8143303723618b31683b52e9c86566aa54c06f0bc27906bcae",  # wstETH/WETH -> lltv 91.5%, oracle: Chainlink wstETH-stETH Exchange Rate
        "0xa5b7ae7654d5041c28cb621ee93397394c7aee6c6e16c7e0fd030128d87ee1a3",  # WETH/USDC -> lltv 86%, oracle: Chainlink ETH/USD but there is no oracle for USDC/USD
        "0x01550b8779f4ca978fc16591537f3852c02c3491f597db93d9bb299dcbf5ddbe",  # WETH/USDT -> lltv 86%, oracle: Chainlink ETH/USD but there is no oracle for USDT/USD
        "0x1cfe584af3db05c7f39d60e458a87a8b2f6b5d8c6125631984ec489f1d13553b",  # WBTC/USDC -> lltv 86%, oracle: Chainlink WBTC/USD but there is no oracle for USDC/USD
        "0x2476bb905e3d94acd7b402b3d70d411eeb6ace82afd3007da69a0d5904dfc998",  # WBTC/USDT -> lltv 86%, oracle: Chainlink WBTC/USD but there is no oracle for USDT/USD
        "0x9eacb622c6ef9c2f0fa5f1fda58a8702eb8132d8f49783f6eea6acc3a398e741",  # WBTC/ETH-> lltv 86%, oracle: Chainlink BTC/USD and ETH/USD
        "0x267f344f5af0d85e95f253a2f250985a9fb9fca34a3342299e20c83b6906fc80",  # WPOL/USDT -> lltv 77%, oracle: Chainlink WPOL/USD, but there is no oracle for USDT/USD
        "0x7506b33817b57f686e37b87b5d4c5c93fdef4cffd21bbf9291f18b2f29ab0550",  # WPOL/USDC -> lltv 77%, oracle: Chainlink WPOL/USD, but there is no oracle for USDC/USD
        "0xd1485762dd5256b99530b6b07ab9d20c8d31b605dd5f27ad0c6dec2a18179ac6",  # compWETH/USDC -> lltv 86%, oracle: Chainlink ETH/USD and vault conversion rate for compoundWETH metamorpho vault
        "0xa8c2e5b31d1f3fb6c000bd49355d091f71e7c866fcb74a1cb2562ef67157bc2a",  # compWETH/USDT -> lltv 86%, oracle: Chainlink ETH/USD and vault conversion rate for compoundWETH metamorpho vault
    ],
}

MARKETS_RISK_2 = {
    Chain.MAINNET: [
        "0x85c7f4374f3a403b36d54cc284983b2b02bbd8581ee0f3c36494447b87d9fcab",  # sUSDe/USDC -> lltv 91.5%, oracle: sUSDe vault
        "0x760b14c9003f08ac4bf0cfb02596ee4d6f0548a4fde5826bfd56befb9ed62ae9",  # PT-USDe-31JUL2025 / DAI -> lltv 91.5%, oracle: Pendle PT with LinearDiscountOracle, aggresive interest rate on high utilization
        "0xab0dcab71e65c05b7f241ea79a33452c87e62db387129e4abe15e458d433e4d8",  # PT-USDe-27MAR2025 / DAI -> lltv 91.5%, using aggresive interest rate curve and using discounted oracle
        "0xa458018cf1a6e77ebbcc40ba5776ac7990e523b7cc5d0c1e740a4bbc13190d8f",  # PT-USDS-14AUG2025 / DAI -> lltv 96.5%, oracle: Pendle PT exchange rate(PT to asset) USDS. No price oracle for DAI, USDS = DAI.
        "0x74ef8d7022b0ef0c0e6dc001fbda3c8bd9a3e706f03bb559c833e1dce7302d3a",  # Curve TricryptoUSDC LP / crvUSD -> lltv 86%, collaterals: ETH, USDC, WBTC
        "0x1c4b9ce834604969d33dc277bd8473d8aee856e5a577c08427b6deeb97cc72d6",  # Curve TricryptoUSDT LP / crvUSD -> lltv 86%, collaterals: ETH, USDT, WBTC
        "0x42e157d3739f9ae3f418f5dd0977b7d51c3a677502afd9f3f594f46cc07dec6a",  # Curve TryLSD LP / crvUSD -> lltv 86%, collaterals: wstETH, rETH, sfrxETH
        "0xbd2a27358bdaf3fb902a0ad17f86d4633f9ac5377941298720b37a4d90deab96",  # Curve TriCRV LP / crvUSD -> lltv 86%, collaterals: crvUSD, ETH, crv
        "0x0cd36e6ecd9d846cffd921d011d2507bc4c2c421929cec65205b3cd72925367c",  # Curve TricryptoLLAMA LP / crvUSD -> collaterals: crvUSD, wstETH, tBTC.
        "0x39d11026eae1c6ec02aa4c0910778664089cdd97c3fd23f68f7cd05e2e95af48",  # sUSDe / DAI -> lltv 86%, same value asset but using hardcoded oracle 1:1 USDe : DAI, sUSDe vault conversion for USDe
        "0xb81eaed0df42ff6646c8daf4fe38afab93b13b6a89c9750d08e705223a45e2ef",  # PT-sUSDE-31JUL2025 / DAI -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) sUSDE. No price oracle for DAI, USDe = DAI.
        "0x1247f1c237eceae0602eab1470a5061a6dd8f734ba88c7cdc5d6109fb0026b28",  # sUSDe / DAI -> lltv 91.5%, same value asset but using hardcoded oracle 1:1 USDe : DAI, sUSDe vault conversion for USDe
        "0xe475337d11be1db07f7c5a156e511f05d1844308e66e17d2ba5da0839d3b34d9",  # sUSDe / DAI -> lltv 41.5%, same value asset but using hardcoded oracle 1:1 USDe : USDC, sUSDe vault conversion for USDe
        "0x8e6aeb10c401de3279ac79b4b2ea15fc94b7d9cfc098d6c2a1ff7b2b26d9d02c",  # USDe / DAI -> lltv 91.5%, same value asset but using hardcoded oracle
        "0xc581c5f70bd1afa283eed57d1418c6432cbff1d862f94eaf58fdd4e46afbb67f",  # USDe / USDC -> lltv 86%, same value asset but using hardcoded oracle
        "0x5f8a138ba332398a9116910f4d5e5dcd9b207024c5290ce5bc87bc2dbd8e4a86",  # ETH+/WETH -> lltv 94.5%, oracle: ETH+ / USD exchange rate adapter and Chainlink: ETH/USD. ETH+ token has monitoring.
        "0x85ab69d50add7daa0934b5224889af0a882f2e3b4572d82c771dd0875f4eaa9b",  # pufETH/WETH -> lltv 94.5%, oracle: pufETH vault exchange rate. Alike assets.
        "0xbf02d6c6852fa0b8247d5514d0c91e6c1fbde9a168ac3fd2033028b5ee5ce6d0",  # LBTC/USDC -> lltv 86%, oracle: Redstone LBTC / BTC Redstone redemption price feed and Chainlink BTC/USD. More info on LBTC/BTC: https://docs.redstone.finance/docs/data/lombard/#how-redstone-delivers-lbtcbtc-fundamental-price
        "0xf6a056627a51e511ec7f48332421432ea6971fc148d8f3c451e14ea108026549",  # LBTC/WBTC -> lltv 94.5%, oracle: readstone exchange rate LBTC/BTC and chainlink WBTC/BTC
        "0xdb8938f97571aeab0deb0c34cf7e6278cff969538f49eebe6f4fc75a9a111293",  # ETH+/USDC -> lltv 86%, oracle: ETH+ / USD exchange rate adapter and Chainlink: USDC/USD. ETH+ token has monitoring.
        "0xc6ae8e71e11ef511acee3f6cc6ad2af67b862877d459e3789905f537c85db5e3",  # PT-sUSDE-25SEP2025/DAI -> lltv 91.5%, oracle: PendleSparkLinearDiscountOracle with linear discount oracle for sUSDE. No price oracle for DAI, USDe = DAI.
        "0xe4cfbee9af4ad713b41bf79f009ca02b17c001a0c0e7bd2e6a89b1111b3d3f08",  # tBTC/USDC -> lltv 77%, oracle: tBTC/USD UMA oracle that captures OEV and USDC/USD UMA oracle.
        "0x7a5d67805cb78fad2596899e0c83719ba89df353b931582eb7d3041fd5a06dc8",  # PT-USDe-25SEP2025/USDC -> lltv 91.5%, oracle: Steakhouse oracle with backup oracle. Main oracle is Pendle PT exchange rate(PT to asset) USDe. Backup oracle is Pendle PT and Chainlink USDe/USD.
        "0x3e37bd6e02277f15f93cd7534ce039e60d19d9298f4d1bc6a3a4f7bf64de0a1c",  # PT-sUSDE-25SEP2025/USDC -> lltv 91.5%, oracle: Steakhouse oracle with backup oracle. Main oracle is Pendle PT exchange rate(PT to asset) sUSDe. Backup oracle is Pendle PT and Chainlink sUSDe/USD.
        "0x45d97c66db5e803b9446802702f087d4293a2f74b370105dc3a88a278bf6bb21",  # PT-USDe-25SEP2025/DAI -> lltv 91.5%, oracle: PendlePT with LinearDiscountOracle. No price oracle for DAI, USDe = DAI.
        "0x05702edf1c4709808b62fe65a7d082dccc9386f858ae460ef207ec8dd1debfa2",  # PT-sUSDE-27NOV2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) sUSDe. No price oracle for USDC, sUSDe = USDC.
        "0x534e7046c3aebaa0c6c363cdbeb9392fc87af71cc16862479403a198fe04b206",  # PT-USDe-27NOV2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) USDe. No price oracle for USDC, USDe = USDC.
        "0x550edc2e9fe71158ccfa7c478a31f4e60ef508d94ada3931dc2aee4f666f8f81",  # yvUSDC-1/USDC -> lltv 91.5%, oracle: yvUSDC-1 vault rate.
        "0x973e9dd45799efe8775417bcc420a3ab84a583587b2108985746e2fe201d0c83",  # YFI/USDC -> lltv 77%, oracle: Chainlink YFI/USD and Chainlink USDC/USD.
        "0xb8fef900b383db2dbbf4458c7f46acf5b140f26d603a6d1829963f241b82510e",  # OETH/USDC -> lltv 86%, oracle: Chainlink ETH/USD and Chainlink USDC/USD. OETH = ETH
    ],
    Chain.BASE: [
        "0x6aa81f51dfc955df598e18006deae56ce907ac02b0b5358705f1a28fcea23cc0",  # wstETH/WETH -> lltv 96.5%, oracle: Chainlink wstETH-stETH Exchange Rate
        "0x6600aae6c56d242fa6ba68bd527aff1a146e77813074413186828fd3f1cdca91",  # cbETH/WETH -> lltv 96.5%, oracle: cbETH-ETH logocbETH-ETH Exchange Rate
        "0x78d11c03944e0dc298398f0545dc8195ad201a18b0388cb8058b1bcb89440971",  # weETH/WETH -> lltv 91.5%, oracle: Chainlink weETH / eETH Exchange Rate
        "0xfd0895ba253889c243bf59bc4b96fd1e06d68631241383947b04d1c293a0cfea",  # weETH/WETH -> lltv 94.5%, oracle: Chainlink weETH / eETH Exchange Rate
        "0xdaa04f6819210b11fe4e3b65300c725c32e55755e3598671559b9ae3bac453d7",  # AERO/USDC -> lltv 62.5%, oracle: Chainlink AERO/USD and Chainlink USDC/USD
        "0x5189c48e1d333d250642a96b90dc926c53f897d8b8f9e8fea71a4b14e9053fde",  # steakSUSDS/USDC -> lltv: 96.5%, oracle: Maker's SSR oracle for sUSDS / USDS and dummy oracle for USDC returns 1. USDS = USDC
        "0xdba352d93a64b17c71104cbddc6aef85cd432322a1446b5b65163cbbc615cd0c",  # cbETH/USDC -> lltv 86.5%, oracle: Chainlink cbETH/ETH and Chainlink ETH/USD and Chainlink USDC/USD -> but low liquidity
        "0x7f90d72667171d72d10d62b5828d6a5ef7254b1e33718fe0c1f7dcf56dd1edc7",  # bsdETH/WETH -> lltv 91.5%, oracle: bsdETH total supply. bsdETH token has internal monitoring.
        "0x144bf18d6bf4c59602548a825034f73bf1d20177fc5f975fc69d5a5eba929b45",  # wsuperOETHb/WETH -> lltv 91.5%, oracle: Vault exchange rate for wsuperOETHb/superOETHb, superOETHb=ETH. wsuperOETHb token has internal monitoring.
        "0x67a66cbacb2fe48ec4326932d4528215ad11656a86135f2795f5b90e501eb538",  # superOETHb/USDC -> lltv 77%, oracle: Chainlink ETH/USD and Chainlink USDC/USD, 1ETH=1superOETHb
    ],
    Chain.KATANA: [
        "0xfe6cb1b88d8830a884f2459962f4b96ae6e38416af086b8ae49f5d0f7f9fc0cd",  # POL/vbUSDC -> lltv 77%, oracle: Chainlink POL/USD and Chainlink USDC/USD
        "0xdf0f160d591f02931e44010763f892a51a480257a5ff21c41ebff874b0c7d258",  # BTCK/vbUSDT -> lltv 77%, oracle: Redstone BTC/USD
        "0x0e9d558490ed0cd523681a8c51d171fd5568b04311d0906fec47d668fb55f5d9",  # BTCK/vbUSDC -> lltv 77%, oracle: Redstone BTC/USD
        "0x071ed2047610c7b33e1540e49fcc0a6852cb783cca0dd7dc428f32fd791a020f",  # wstETH/AUSD -> lltv 86%, oracle: RedStone Price Feed for wstETH. USD=AUSD.
        "0xa7cd449cc319d65be3d0926d6b6f599a8c3434bd95ba3e91bbf1ee5e80e72b56",  # LBTC/vbUSDC -> lltv 86%, oracle: RedStone Price Feed for LBTC_FUNDAMENTAL and RedStone BTC/USD. USD=vbUSDC.
    ],
    Chain.POLYGON: [
        "0x41e537c46cc0e2f82aa69107cd72573f585602d8c33c9b440e08eaba5e8fded1",  # MATICX/USDT -> lltv 77%, oracle: Chainlink Calculated MaticX / USD, but there is no oracle for USDT/USD. Maticx has liquidity around 7M without slippage, around 1.7M USD. Withdrawing Matic will take 90 checkpoints (2-3 days) as per Polygon's native unstaking
        "0x1947267c49c3629c5ed59c88c411e8cf28c4d2afdb5da046dc8e3846a4761794",  # MATICX/USDC -> lltv 77%, oracle: Chainlink Calculated MaticX / USD, but there is no oracle for USDC/USD. Maticx has liquidity around 7M without slippage, around 1.7M USD. Withdrawing Matic will take 90 checkpoints (2-3 days) as per Polygon's native unstaking
        "0x8513df298cab92cafba1bae394420b7150aa40a5fac649c7168404bd5174a54c",  # sACRED/USDC -> lltv 86%, oracle: Redstone ACRED/USD which is connect only to securitize-api. Using vault conversion rate for sACRED/ACRED
    ],
}

MARKETS_RISK_3 = {
    Chain.MAINNET: [
        "0x0cd36e6ecd9d846cffd921d011d2507bc4c2c421929cec65205b3cd72925367c",  # Curve TricryptoLLAMA LP / crvUSD -> collaterals: crvUSD, wstETH, tBTC.
        "0x198132864e7974fb451dfebeb098b3b7e7e65566667fb1cf1116db4fb2ad23f9",  # PT-LBTC-27MAR2025 / WBTC, lltv 86%, oracle: Pendle PT exchange rate, readstone exchange rate LBTC/BTC and chainlink WBTC/BTC.
        "0x8a0384fe5b1a68ff217845752287f432029b20754fbce577b6a5f8a80030a825",  # PT-LBTC-26JUN2025 / WBTC, lltv 91.5%, oracle: Pendle PT exchange rate, readstone exchange rate LBTC/BTC
        "0xba761af4134efb0855adfba638945f454f0a704af11fc93439e20c7c5ebab942",  # rsETH/WETH -> lltv 94.5%, oracle: origami rsETH/ETH which calls KELP_LRT_ORACLE.rsETHPrice(). Oracle address: https://etherscan.io/address/0x349A73444b1a310BAe67ef67973022020d70020d
        "0xa0534c78620867b7c8706e3b6df9e69a2bc67c783281b7a77e034ed75cee012e",  # ezETH/WETH -> lltv 94.5%, oracle: origami ezETH/ETH which calls renzoOracle()).calculateRedeemAmount(). It is hypothetical price, not the actual price.
        "0x8e7cc042d739a365c43d0a52d5f24160fa7ae9b7e7c9a479bd02a56041d4cf77",  # USR/USDC -> lltv 91.5%, oracle: USR/USD price aggregator which is checking reserves and defining max price as 1
        "0x97bb820669a19ba5fa6de964a466292edd67957849f9631eb8b830c382f58b7f",  # MKR/USDC
        "0x718af3af39b183758849486340b69466e3e89b84b7884188323416621ee91cb7",  # UNI/USDC
        "0x61765602144e91e5ac9f9e98b8584eae308f9951596fd7f5e0f59f21cd2bf664",  # weETH/USDC
        "0x9c765f69d8a8e40d2174824bc5107d05d7f0d0f81181048c9403262aeb1ab457",  # LINK/USDC
        "0xb7ad412532006bf876534ccae59900ddd9d1d1e394959065cb39b12b22f94ff5",  # agETH/WETH -> lltv 91.5%, oracle: rsETH/ETH exchange rateainlink ETH/USD. Alike assets.
        "0x1eda1b67414336cab3914316cb58339ddaef9e43f939af1fed162a989c98bc20",  # USD0++/USDC -> lltv 96.5%, oracle: Naked USD0++ price feed adapter
        "0xf9e56386e74f06af6099340525788eec624fd9c0fc0ad9a647702d3f75e3b6a9",  # clUSD/USDC -> lltv 96.5%, oracle: Chainlink clUSD/USD
        "0xeec6c7e2ddb7578f2a7d86fc11cf9da005df34452ad9b9189c51266216f5d71b",  # PT-wstUSR-25SEP2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) wstUSR
        "0xd9e34b1eed46d123ac1b69b224de1881dbc88798bc7b70f504920f62f58f28cc",  # wstUSR/USDC -> lltv 91.5%, oracle: wstUSR vault rate. USR/USD price aggregator which is checking reserves and defining max price as 1
        "0x729badf297ee9f2f6b3f717b96fd355fc6ec00422284ce1968e76647b258cf44",  # syrupUSDC/USDC -> lltv 91.5%, oracle: syrupUSDC MaplePool vault rate. Oracle is using convertToAssets() to get the price but maple pool returns different amount, it should use convertToExitAssets() instead.
        "0xa3819a7d2aee958ca0e7404137d012b51ea47d051db69d94656956eff8c80c23",  # PT-syrupUSDC-28AUG2025/USDC -> lltv 86%, oracle: Pendle PT exchange rate(PT to asset) syrupUSDC.
        "0xfae6c3fca4d2fe61c62d29541e84a728b660a0dbc99217750c1080a8fc7d0e45",  # PT-eUSDE-14AUG2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) eUSDE. No price oracle for USDC, USDe = USDC.
        "0x53ed197357128ed96070e20ba9f5af4250cda6c67dcac5246876beb483f51303",  # sDOLA/USDC -> lltv 91.5%, oracle: sDOLA vault rate. DOLA = USDC hardcoded oracle.
        "0xce68c7aa336675e42bbc8eaa8b5ecc7ebd816bf8625b5316330c6ac2dabc4cf2",  # SolvBTC/BTC -> lltv 94.5%, oracle: upgradeable MetaOracleDeviationTimelock with prime oracle morpho oracle with 1:1 hardcoded rate
        "0x7a7018e22a8bb2d08112eae9391e09f065a8ae7ae502c1c23dc96c21411a6efd",  # EIGEN/USDC -> lltv 77%, oracle: Redstone EIGEN/USD. USD = USDC.
        "0xb8afc953c3cc8077b4a4bf459bede8d3f80be45ca1f244e4bca13b7b1030eed5",  # PT-syrupUSDC-30OCT2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) syrupUSDC. syrupUSDC = USDC.
    ],
    Chain.BASE: [
        "0x9a697eb760dd12aaea23699c96ea2ebbfe48b7af64138d92c4d232b9ed380024",  # PT-LBTC-29MAY2025/cbBTC -> lltv 91.5%, oracle: Pendle PT with LinearDiscountOracle. Higher lltv than PT-LBTC-27MAR2025 / WBTC.
        "0x4944a1169bc07b441473b830308ffe5bb535c10a9f824e33988b60738120c48e",  # LBTC/cbBTC -> lltv 91.5%, oracle: Custom moonwell oracle. Base feed is fetched from upgradeable oracle which uses 2 oracles. Primary oracle is redstone oracle, if the price changes more than 2% than it uses fallback oracle chainlink oracle. Chainlink didn't have an exchange rate feed. Redstone was the only provider for the LBTC reserves.
        "0x214c2bf3c899c913efda9c4a49adff23f77bbc2dc525af7c05be7ec93f32d561",  # wrsETH/WETH -> lltv 94.5%, oracle: Chainlink wrsETH/ETH exchange rate
        "0x6a331b22b56c9c0ee32a1a7d6f852d2c682ea8b27a1b0f99a9c484a37a951eb7",  # weETH/USDC -> lltv 77%, oracle: Chainlink weETH / eETH Exchange Rate and Chainlink ETH/USD and Chainlink USDC/USD
        "0x52a2a376586d0775e3e80621facc464f6e96d81c8cb70fd461527dde195a079f",  # LBTC/USDC -> lltv 86%, oracle: RedStone Price Feed for LBTC/BTC  and Chainlink BTC/USD
        "0x30767836635facec1282e6ef4a5981406ed4e72727b3a63a3a72c74e8279a8d7",  # LBTC/cbBTC -> lltv 94.5%, oracle: RedStone Price Feed for LBTC_FUNDAMENTAL: https://app.redstone.finance/app/feeds/base/lbtc_fundamental/
        "0x0138c47c8f7e0a785ec20a46edc6dc7747c8cd6e318d02f6506a5b6a5f5be7b0",  # PT-LBTC-scaled18-25SEP2025/cbBTC -> lltv 91.5%, oracle: Pendle PT exchange ratePT with TWAP 900s
    ],
    Chain.KATANA: [],
    Chain.POLYGON: [],
}

MARKETS_RISK_4 = {
    Chain.MAINNET: [
        "0x3c83f77bde9541f8d3d82533b19bbc1f97eb2f1098bb991728acbfbede09cc5d",  # rETH/WETH -> lltv 94.5%, oracle: gravita rETH/ETH. Can change owner and aggregator.
        "0xe95187ba4e7668ab4434bbb17d1dfd7b87e878242eee3e73dac9fdb79a4d0d99",  # EIGEN/USDC
        "0x444327b909aa41043cc4f20209eefb2fbb37f1c38ff9ca312374a4ecc3f0a871",  # solvBTC/USDC
        "0x2287407f0f42ad5ad224f70e4d9da37f02770f79959df703d6cfee8afc548e0d",  # STONE/WETH -> centralization risk
        "0xf78b7d3a62437f78097745a5e3117a50c56a02ec5f072cba8d988a129c6d4fb6",  # beraSTONE/WETH -> centralization riskink ETH/USD
        "0xcacd4c39af872ddecd48b650557ff5bcc7d3338194c0f5b2038e0d4dec5dc022",  # rswETH/WETH -> unknown asset
        "0x0eed5a89c7d397d02fd0b9b8e42811ca67e50ed5aeaa4f22e506516c716cfbbf",  # pufETH/WETH -> low liquidity market
        "0x7e9c708876fa3816c46aeb08937b51aa0461c2af3865ecb306433db8a80b1d1b",  # pufETH/USDC -> low liquidity market
        "0x514efda728a646dcafe4fdc9afe4ea214709e110ac1b2b78185ae00c1782cc82",  # swBTC/WBTC -> same asset, check swBTC liquidity before moving up
        "0x20c488469064c8e2f892dab33e8c7a631260817f0db57f7425d4ef1d126efccb",  # Re7wstETH/WETH -> unknown asset
        "0xd925961ad5df1d12f677ff14cf20bac37ea5ef3b325d64d5a9f4c0cc013a1d47",  # stUSD/USDC -> lltv 96.5%, oracle: stUSD vault rate. Angle transmuter handles USDA -> USDC conversion.
        "0xbf6687cb042a09451e66ebc11d7716c49fb8ccc75f484f7fab0eed6624bd5838",  # mMEV/USDC -> lltv 91.5%, oracle: Midas price oracle mMEV/USD. More info at: https://docs.midas.app/defi-integration/price-oracle
        "0x83b7ad16905809ea36482f4fbf6cfee9c9f316d128de9a5da1952607d5e4df5e",  # csUSDL/USDC -> lltv 96.5%, oracle: wUSDL / USDL vault rate.
        "0xa3819a7d2aee958ca0e7404137d012b51ea47d051db69d94656956eff8c80c23",  # PT-syrupUSDC-28AUG2025/USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) syrupUSDC.
        "0xe1b65304edd8ceaea9b629df4c3c926a37d1216e27900505c04f14b2ed279f33",  # RLP/USDC -> lltv 86%, oracle: RLP oracle where the price is set manually, but must be in bounds. Owner of the proxy is multisig.
        "0x8b1bc4d682b04a16309a8adf77b35de0c42063a7944016cfc37a79ccac0007b6",  # slvlUSD/USDC -> lltv 91.5%, oracle: slvlUSD vault rate. lvlUSD = USDC
        "0x8a71a66ac828c2b6d4f8accce5859aba0822b502f3833bec4aff09479affffdb",  # PT-cUSDO-20NOV2025 / USDC -> lltv 91.5%, oracle: Pendle PT exchange rate(PT to asset) cUSDO. cUSDO = USDC.
        "0x95c28d447950ca6c8bbfd25fc05b80b1fd7a1cdd17a3610b4b3f1ffc8dc2e2ed",  # mHYPER / USDC -> lltv 86%, oracle: MHyperCustomAggregatorFeed
        "0xeb17955ea422baeddbfb0b8d8c9086c5be7a9cfdefb292119a102e981a30062e",  # stcUSD/USDC -> lltv 91.5%, oracle: Ojo Yield Risk Engine stcUSD/cUSD Exchange Rate and RedStone Price Feed for cUSD_FUNDAMENTAL and Chainlink USDC/USD.
        "0xa02ad0cf521ba5e5b20d1bcb98043eb091807e2b3bf26df5aad1ad154a3b8d45",  # PT-RLP-4DEC2025/USDC -> lltv 86%, oracle: Pendle PT exchange rate(PT to asset) RLP. RLP = USDC.
    ],
    Chain.BASE: [
        "0xff0f2bd52ca786a4f8149f96622885e880222d8bed12bbbf5950296be8d03f89",  # USR/USDC -> lltv 91.5%, oracle: pyth USR/USD and qoute pyth USDC/USD
    ],
    Chain.KATANA: [],
    Chain.POLYGON: [],
}

MARKETS_RISK_5 = {
    Chain.MAINNET: [
        "0xbfed072faee09b963949defcdb91094465c34c6c62d798b906274ef3563c9cac",  # srUSD/USDC -> lltv 91.5%, oracle: saving rate module price. rUSD(USD) is underlying asset. rUSD = USDC hardcoded oracle.
        "0x0f9563442d64ab3bd3bcb27058db0b0d4046a4c46f0acd811dacae9551d2b129",  # sdeUSD/USDC -> lltv 91.5%, oracle: sdeUSD vault rate. Redstone oracle deusd/usd price, 24hour heartbeat, deviation 0.2%: https://app.redstone.finance/app/feeds/ethereum-mainnet/deusd_fundamental/
    ],
    Chain.BASE: [],
    Chain.KATANA: [
        "0x16ded80178992b02f7c467c373cfc9f4eee7f0356df672f6a768ec92b2ffdeff",  # yUSD/vbUSDC -> lltv 86%, oracle: yUSD vault rate. yUSD = vbUSDC hardcoded oracle
        "0xd8a93a4cd16f843c385391e208a9a9f2fd75aedfcca05e4810e5fbfcaa6baec6",  # wsrUSD/vbUSDC -> lltv 91.5%, oracle: API3 wsrUSD/rUSD Exchange Rate, rUSD = vbUSDC
    ],
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


def get_chain_name(chain: Chain) -> str:
    """Convert chain to name used in Morpho URLs."""
    if chain == Chain.MAINNET:
        return "ethereum"
    else:
        return chain.name.lower()


def get_market_url(market: Dict[str, Any]) -> str:
    """Generate URL for a Morpho market."""
    chain_id = market["collateralAsset"]["chain"]["id"]
    chain = Chain.from_chain_id(chain_id)
    return f"{MORPHO_URL}/{get_chain_name(chain)}/market/{market['uniqueKey']}"


def get_vault_url(vault_data: Dict[str, Any]) -> str:
    """Generate URL for a Morpho vault."""
    chain_id = vault_data["chain"]["id"]
    chain = Chain.from_chain_id(chain_id)
    return f"{MORPHO_URL}/{get_chain_name(chain)}/vault/{vault_data['address']}"


def bad_debt_alert(markets: List[Dict[str, Any]], vault_name: str = "") -> None:
    """
    Send telegram message if bad debt is detected in any market.

    Args:
        markets: List of market data
        vault_name: Name of the vault (for alert message)
    """
    for market in markets:
        bad_debt = market["badDebt"]["usd"]
        borrowed_tvl = market["state"]["borrowAssetsUsd"]

        # Skip markets with no borrows
        if borrowed_tvl == 0:
            continue

        # Alert if bad debt ratio exceeds threshold
        if bad_debt / borrowed_tvl > BAD_DEBT_RATIO:
            market_url = get_market_url(market)
            market_name = f"{market['collateralAsset']['symbol']}/{market['loanAsset']['symbol']}"

            message = (
                f"🚨 Bad debt detected for Morpho {vault_name}\n"
                f"💹 Market: [{market_name}]({market_url})\n"
                f"💸 Bad debt: ${bad_debt:,.2f} USD\n"
                f"📊 Bad debt ratio: {(bad_debt / borrowed_tvl):.2%}\n"
            )

            send_telegram_message(message, PROTOCOL)


def check_high_allocation(vault_data):
    """
    Send telegram message if high allocation is detected in any market.
    Send another message if total risk level is too high.
    """
    total_assets = vault_data.get("state", {}).get("totalAssetsUsd", 0)
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
        market_supply = allocation.get("supplyAssetsUsd", 0)
        allocation_ratio = min(market_supply / total_assets, 1.0)  # prevent allocation ratio from exceeding 100%

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

        allocation_threshold = get_market_allocation_threshold(market_risk_level, risk_level)
        risk_multiplier = market_risk_level

        if allocation_ratio > allocation_threshold:
            market_url = get_market_url(market)
            market_name = f"{market['collateralAsset']['symbol']}/{market['loanAsset']['symbol']}"
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
    # round total_risk_level to 2 decimal places
    total_risk_level = round(total_risk_level, 2)
    if total_risk_level > MAX_RISK_THRESHOLDS[risk_level]:
        message = (
            f"🔺 High allocation detected in [{vault_name}]({vault_url}) on {chain.name}\n"
            f"🔢 Total risk level: {total_risk_level:.1%} but max acceptable is {MAX_RISK_THRESHOLDS[risk_level]}\n"
            f"🔢 Total assets: ${total_assets:,.2f}\n"
        )
        send_telegram_message(message, PROTOCOL)


def is_yv_collateral_vault(vault_address: str, chain: Chain) -> bool:
    """
    Check if a vault is used as YV collateral by looking in the asset-based config.

    Args:
        vault_address: Address of the vault to check
        chain: Chain the vault is on

    Returns:
        True if vault is used as YV collateral
    """
    if chain not in VAULTS_WITH_YV_COLLATERAL_BY_ASSET:
        return False

    # Check all asset groups for this chain
    for asset_address, vaults in VAULTS_WITH_YV_COLLATERAL_BY_ASSET[chain].items():
        for vault_name, vault_addr in vaults:
            if vault_addr.lower() == vault_address.lower():
                return True

    return False


def get_yv_collateral_vaults_by_asset(chain: Chain) -> Dict[str, List[str]]:
    """
    Get YV collateral vaults organized by asset address.

    Args:
        chain: Chain to get vaults for

    Returns:
        Dictionary with asset address as key and list of vault addresses as value
    """
    result = {}

    if chain not in VAULTS_WITH_YV_COLLATERAL_BY_ASSET:
        return result

    for asset_address, vaults in VAULTS_WITH_YV_COLLATERAL_BY_ASSET[chain].items():
        vault_addresses = [vault[1] for vault in vaults]  # Extract addresses from [name, address] pairs
        result[asset_address.lower()] = vault_addresses

    return result


def group_vaults_by_chain(vaults_data: List[Dict[str, Any]]) -> Dict[Chain, List[Dict[str, Any]]]:
    """Group vaults by their chain."""
    vaults_by_chain = {}
    for vault_data in vaults_data:
        chain = Chain.from_chain_id(vault_data["chain"]["id"])
        if chain not in vaults_by_chain:
            vaults_by_chain[chain] = []
        vaults_by_chain[chain].append(vault_data)
    return vaults_by_chain


def find_yv_vaults_for_asset(
    chain_vaults: List[Dict[str, Any]],
    asset_address: str,
    yv_vault_addresses: List[str],
) -> List[Dict[str, Any]]:
    """Find all YV collateral vaults for a specific asset."""
    asset_yv_vaults = []

    for vault_data in chain_vaults:
        vault_address = vault_data["address"]
        vault_asset_address = vault_data.get("asset", {}).get("address", "").lower()

        # Check if this vault is for the current asset and is YV collateral
        if vault_asset_address == asset_address and vault_address in yv_vault_addresses:
            asset_yv_vaults.append(vault_data)

    return asset_yv_vaults


def calculate_combined_metrics(asset_yv_vaults: List[Dict[str, Any]]) -> tuple[float, float, List[str]]:
    """Calculate combined total assets, liquidity, and vault names for a group of vaults."""
    combined_total_assets = 0
    combined_liquidity = 0
    vault_names = []

    for vault in asset_yv_vaults:
        total_assets = vault["state"]["totalAssetsUsd"] or 0
        liquidity = vault["liquidity"]["usd"] or 0

        # Only include vaults with meaningful assets (>= 10k)
        if total_assets >= 10_000:
            combined_total_assets += total_assets
            combined_liquidity += liquidity
            vault_names.append(vault["name"])

    return combined_total_assets, combined_liquidity, vault_names


def check_combined_liquidity_threshold(
    asset_symbol: str,
    chain: Chain,
    combined_total_assets: float,
    combined_liquidity: float,
    vault_names: List[str],
    vault_count: int,
) -> None:
    """Check if combined liquidity meets threshold and send alert if needed."""
    if combined_total_assets < 10_000:
        print(
            f"Skipping {asset_symbol} combined liquidity check: total assets ${combined_total_assets:,.2f} below threshold"
        )
        return

    combined_liquidity_ratio = combined_liquidity / combined_total_assets

    print(
        f"Combined {asset_symbol} liquidity check: {vault_count} vaults on {chain.name}, "
        f"${combined_total_assets:,.2f} total assets, "
        f"{combined_liquidity_ratio:.1%} liquidity ratio"
    )

    if combined_liquidity_ratio < LIQUIDITY_THRESHOLD_YV_COLLATERAL:
        vault_list = ", ".join(vault_names)
        message = (
            f"⚠️ Low combined liquidity detected for {asset_symbol} YV collateral vaults on {chain.name}\n"
            f"🚨 Combined vaults: {vault_list}\n"
            f"🚨 Min liquidity is {LIQUIDITY_THRESHOLD_YV_COLLATERAL:.1%} of total assets.\n"
            f"💰 Combined liquidity: {combined_liquidity_ratio:.1%} of total assets\n"
            f"💵 Combined liquidity: ${combined_liquidity:,.2f}\n"
            f"📊 Combined total assets: ${combined_total_assets:,.2f}"
        )
        send_telegram_message(message, PROTOCOL)


def check_yv_collateral_liquidity_for_chain(chain: Chain, chain_vaults: List[Dict[str, Any]]) -> None:
    """Check combined liquidity for YV collateral vaults on a specific chain."""
    yv_vaults_by_asset = get_yv_collateral_vaults_by_asset(chain)

    # Check each asset group for combined liquidity
    for asset_address, yv_vault_addresses in yv_vaults_by_asset.items():
        # Find all vaults for this asset that are YV collateral
        asset_yv_vaults = find_yv_vaults_for_asset(chain_vaults, asset_address, yv_vault_addresses)

        if not asset_yv_vaults:
            continue

        # Get asset symbol from first vault
        asset_symbol = asset_yv_vaults[0].get("asset", {}).get("symbol", "UNKNOWN")

        # Calculate combined metrics for this asset
        (
            combined_total_assets,
            combined_liquidity,
            vault_names,
        ) = calculate_combined_metrics(asset_yv_vaults)

        # Check threshold and alert if needed
        check_combined_liquidity_threshold(
            asset_symbol,
            chain,
            combined_total_assets,
            combined_liquidity,
            vault_names,
            len(asset_yv_vaults),
        )


def check_individual_liquidity_for_chain(chain: Chain, chain_vaults: List[Dict[str, Any]]) -> None:
    """Check individual liquidity for non-YV collateral vaults on a specific chain."""
    for vault_data in chain_vaults:
        vault_address = vault_data["address"]
        if not is_yv_collateral_vault(vault_address, chain):
            check_low_liquidity(vault_data)


def check_low_liquidity_combined(vaults_data: List[Dict[str, Any]]) -> None:
    """
    Check liquidity for vaults, with special logic for VAULTS_WITH_YV_COLLATERAL_BY_ASSET.
    For YV collateral vaults, combine all vaults with the same asset and check if
    the combined liquidity passes the threshold.
    """
    # Group vaults by chain for processing
    vaults_by_chain = group_vaults_by_chain(vaults_data)

    # Process each chain separately
    for chain, chain_vaults in vaults_by_chain.items():
        # Check combined liquidity for YV collateral vaults
        check_yv_collateral_liquidity_for_chain(chain, chain_vaults)

        # Check individual liquidity for non-YV collateral vaults
        check_individual_liquidity_for_chain(chain, chain_vaults)


def check_low_liquidity(vault_data):
    """
    Send telegram message if low liquidity is detected.
    """
    vault_name = vault_data["name"]
    vault_url = get_vault_url(vault_data)
    total_assets = vault_data["state"]["totalAssetsUsd"]
    liquidity = vault_data["liquidity"]["usd"]
    chain = Chain.from_chain_id(vault_data["chain"]["id"])

    # Return early if total_assets is None or 0 or less than 10k
    if not total_assets or total_assets < 10_000:
        return

    # Default liquidity to 0 if it's None
    liquidity = liquidity or 0
    liquidity_ratio = liquidity / total_assets

    # standard liquidity check (YV collateral vaults are handled separately)
    if liquidity_ratio < LIQUIDITY_THRESHOLD:
        message = (
            f"⚠️ Low liquidity detected in [{vault_name}]({vault_url}) on {chain.name}\n"
            f"💰 Liquidity: {liquidity_ratio:.1%} of total assets\n"
            f"💵 Liquidity: ${liquidity:,.2f}\n"
            f"📊 Total Assets: ${total_assets:,.2f}"
        )
        send_telegram_message(message, PROTOCOL)


def main() -> None:
    """
    Check markets for low liquidity, high allocation and bad debt.
    Send telegram message if data cannot be fetched.
    """
    print("Checking Morpho markets...")

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
                asset {
                    address
                    symbol
                    name
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

    try:
        response = requests.post(API_URL, json=json_data, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        send_telegram_message(
            f"🚨 Problem with fetching data for Morpho markets: {str(e)} 🚨",
            PROTOCOL,
            True,
            True,
        )
        return

    data = response.json()
    if "errors" in data:
        error_msg = data["errors"][0]["message"] if data["errors"] else "Unknown GraphQL error"
        send_telegram_message(
            f"🚨 GraphQL error when fetching Morpho data: {error_msg} 🚨",
            PROTOCOL,
            True,
            True,
        )
        return

    vaults_data = data.get("data", {}).get("vaults", {}).get("items", [])
    if len(vaults_data) == 0:
        send_telegram_message("🚨 No vaults data found 🚨", PROTOCOL)
        return

    # Check combined liquidity for all vaults (handles YV collateral grouping)
    check_low_liquidity_combined(vaults_data)

    for vault_data in vaults_data:
        # Check high allocation for each vault
        check_high_allocation(vault_data)

        # Check bad debt for each market in the vault
        vault_markets = []
        for allocation in vault_data["state"]["allocation"]:
            market_supply_usd = allocation.get("market", {}).get("state", {}).get("supplyAssetsUsd")
            if allocation["enabled"] and (market_supply_usd or 0) > 0:
                market = allocation["market"]
                if market["collateralAsset"] is not None:
                    # market without collateral asset is idle asset
                    vault_markets.append(market)

        bad_debt_alert(vault_markets, vault_data["name"])


if __name__ == "__main__":
    main()
