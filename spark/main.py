from web3 import Web3
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message

load_dotenv()

PROTOCOL = "SPARK"
provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")

with open("aave/abi/AToken.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_atoken = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_atoken = abi_data

mainnet_addresses = [
    [
        "0x78f897F0fE2d3B5690EbAe7f19862DEacedF10a7",
        "0x83F20F44975D03b1b09e64809B757c47f942BEeA",
    ],  # asdai, sdai
    [
        "0x377C3bd93f2a2984E1E7bE6A5C22c525eD4A4815",
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    ],  # ausdc, usdc
    [
        "0x4197ba364AE6698015AE5c1468f54087602715b2",
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    ],  # awbtc, wbtc
    [
        "0x59cD1C87501baa753d0B5B5Ab5D8416A45cD71DB",
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    ],  # aweth, weth
    [
        "0x12B54025C112Aa61fAce2CDB7118740875A566E9",
        "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
    ],  # awsteth, wsteth
    [
        "0x4DEDf26112B3Ec8eC46e7E31EA5e123490B05B8B",
        "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    ],  # adai, dai
    [
        "0xe7dF13b8e3d6740fe17CBE928C7334243d86c92f",
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    ],  # ausdt, usdt
    [
        "0x9985dF20D7e9103ECBCeb16a84956434B6f06ae8",
        "0xae78736Cd615f374D3085123A210448E74Fc6393",
    ],  # areth, reth
    [
        "0xb3973D459df38ae57797811F2A1fd061DA1BC123",
        "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    ],  # spcwbtc, cbwbtc
    [
        "0x3CFd5C0D4acAA8Faee335842e4f31159fc76B008",
        "0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee",
    ],  # spweeth, weeth
]

# TODO: Add different threshold UR's for each asset
THRESHOLD_UR = 0.96
THRESHOLD_UR_NOTIFICATION = 0.99


# Build contract function
def build_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_atoken)
    return contract


def print_stuff(chain_name, token_name, ur):
    if ur > THRESHOLD_UR:
        message = (
            "🚨 **BEEP BOP** 🚨\n"
            f"💎 Market asset: {token_name}\n"
            f"📊 Utilization rate: {ur:.2%}\n"
            f"🌐 Chain: {chain_name}"
        )
        disable_notification = True
        if ur > THRESHOLD_UR_NOTIFICATION:
            disable_notification = False
        send_telegram_message(message, PROTOCOL, disable_notification)


# Function to process assets for a specific network
def process_assets(chain_name, addresses, provider_url):
    for atoken_address, underlying_token_address in addresses:
        # Build contracts
        atoken = build_contract(atoken_address, provider_url)
        underlying_token = build_contract(underlying_token_address, provider_url)

        # Get total supply and available balance
        ts = atoken.functions.totalSupply().call()
        av = underlying_token.functions.balanceOf(atoken_address).call()

        # Calculate debt and utilization rate
        debt = ts - av
        ur = debt / ts if ts != 0 else 0

        token_name = underlying_token.functions.symbol().call()
        print_stuff(chain_name, token_name, ur)


# Main function
def main():
    print("Processing Mainnet assets...")
    process_assets("Mainnet", mainnet_addresses, provider_url_mainnet)


# Run the main function
if __name__ == "__main__":
    main()
