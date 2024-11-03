from web3 import Web3
from dotenv import load_dotenv
import os, json, datetime
from utils.telegram import send_telegram_message

# Constants
DURATION = 1800  # 30 minutes
THRESHOLD_RATIO = 0.95
PROTOCOL = "PENDLE"

# Load environment variables
load_dotenv()

# Provider URLs
PROVIDER_URL_MAINNET = os.getenv("PROVIDER_URL_MAINNET")
PROVIDER_URL_ARB = os.getenv("PROVIDER_URL_ARBITRUM")

# Oracle address
ORACLE_ADDRESS = "0x14418800E0B4C971905423aa873e83355922428c"

# Vault addresses
ARBITRUM_VAULTS = [
    "0x044E75fCbF7BD3f8f4577FF317554e9c0037F145",  # weeth
    "0x1Dd930ADD968ff5913C3627dAA1e6e6FCC9dc544",  # kelp dao eth
    "0x34a2b066AF16409648eF15d239E656edB8790ca0",  # usde
]

MAINNET_VAULTS = [
    "0xe5175a2EB7C40bC5f0E9DE4152caA14eab0fFCb7",  # weeth symbiotic
    "0xDDa02A2FA0bb0ee45Ba9179a3fd7e65E5D3B2C90",  # ageth
    "0x2F2BBc50DB252eeADD2c9B9197beb6e5Aef87e48",  # ena
    "0x57a8b4061AA598d2Bb5f70C5F931a75C9F511fc8",  # lbtc corn
    "0x57fC2D9809F777Cd5c8C433442264B6E8bE7Fce4",  # sUSDe
]


# Load ABI files
def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


ABI_ORACLE = load_abi("pendle/abi/PendleYPLpOracle.json")
ABI_VAULT = load_abi("common-abi/YearnV3Vault.json")
ABI_STRATEGY = load_abi("pendle/abi/PendleStrategy.json")
ABI_MARKET = load_abi("pendle/abi/PendleMarket.json")


def get_ratio_for_market(market, oracle):
    pt_ratio = oracle.functions.getPtToAssetRate(market, DURATION).call()
    pt_ratio_readable = pt_ratio / 1e18
    print(f"PT to Asset Ratio for {market}: {pt_ratio_readable}")
    return pt_ratio_readable


def get_strategies_from_vault(vault, w3):
    vault_contract = w3.eth.contract(address=vault, abi=ABI_VAULT)
    strategies = vault_contract.functions.get_default_queue().call()
    name = vault_contract.functions.name().call()
    strategies_with_assets = [
        strategy
        for strategy in strategies
        if w3.eth.contract(address=strategy, abi=ABI_STRATEGY)
        .functions.totalAssets()
        .call()
        > 1e9
        and not w3.eth.contract(address=strategy, abi=ABI_STRATEGY)
        .functions.isExpired()
        .call()
    ]
    print(f"Strategies for {name}: {strategies_with_assets}")
    return strategies_with_assets, name


def get_market_from_strategy(strategy_address, w3):
    strategy = w3.eth.contract(address=strategy_address, abi=ABI_STRATEGY)
    market_address = strategy.functions.market().call()
    market = w3.eth.contract(address=market_address, abi=ABI_MARKET)
    if market.functions.isExpired().call():
        print(f"Market for {strategy_address} is expired")
        return None, None

    expiry = market.functions.expiry().call()
    expiry = datetime.datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Market for {strategy_address}: {market_address}")
    print(f"Expiry for {strategy_address}: {expiry}")
    return market_address, expiry


def get_data_for_chain(chain):
    if chain == "mainnet":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_MAINNET))
        vaults = MAINNET_VAULTS
    elif chain == "arbitrum":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_ARB))
        vaults = ARBITRUM_VAULTS
    else:
        raise ValueError("Invalid chain")

    print(f"Processing {chain} assets...")
    print(f"Vaults: {vaults}")

    oracle = w3.eth.contract(address=ORACLE_ADDRESS, abi=ABI_ORACLE)
    for vault in vaults:
        strategies, name = get_strategies_from_vault(vault, w3)
        for strategy in strategies:
            market, expiry = get_market_from_strategy(strategy, w3)
            if not market:
                continue
            ratio = get_ratio_for_market(market, oracle)
            print(f"Market: {market}, Ratio: {ratio:.2f}")
            if ratio < THRESHOLD_RATIO:
                message = (
                    "🚨 **Pendle PT Ratio** 🚨\n"
                    f"💎 Market: {market}\n"
                    f"📊 PT to Asset Ratio: {ratio:.2f}\n"
                    f"🌐 Chain: {chain}\n"
                    f"🕒 Expiry: {expiry}\n"
                    f"🏦 Vault: {name}"
                )
                send_telegram_message(message, PROTOCOL, False)


def main():
    get_data_for_chain("mainnet")
    get_data_for_chain("arbitrum")


if __name__ == "__main__":
    main()
