from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")

with open("aave/abi/AToken.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_atoken = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_atoken = abi_data

mainnet_addresses = [
    "0x78f897F0fE2d3B5690EbAe7f19862DEacedF10a7", # asdai
    "0x83F20F44975D03b1b09e64809B757c47f942BEeA", # sdai
    "0x377C3bd93f2a2984E1E7bE6A5C22c525eD4A4815", # ausdc
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", # usdc
    "0x4197ba364AE6698015AE5c1468f54087602715b2", # awbtc
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", # wbtc
    "0x59cD1C87501baa753d0B5B5Ab5D8416A45cD71DB", # aweth
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", # weth
    "0x12B54025C112Aa61fAce2CDB7118740875A566E9", # awsteth
    "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0", # wsteth
    "0x4DEDf26112B3Ec8eC46e7E31EA5e123490B05B8B", # adai
    "0x6B175474E89094C44Da98b954EedeAC495271d0F", # dai
    "0xe7dF13b8e3d6740fe17CBE928C7334243d86c92f", # ausdt
    "0xdAC17F958D2ee523a2206206994597C13D831ec7", # usdt
    "0x9985dF20D7e9103ECBCeb16a84956434B6f06ae8", # areth
    "0xae78736Cd615f374D3085123A210448E74Fc6393" # reth
]

# TODO: Add different threshold UR's for each asset
THRESHOLD_UR = 0.95

# Build contract function
def build_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_atoken)
    return contract

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_SPARK")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_SPARK")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")

def print_stuff(chain_name, token_name, ur):
    if ur > THRESHOLD_UR:
        message = (
            "🚨 **BEEP BOP** 🚨\n"
            f"💎 Market asset: {token_name}\n"
            f"📊 Utilization rate: {ur:.2%}\n"
            f"🌐 Chain: {chain_name}"
        )
        print(message)
        send_telegram_message(message)

# Function to process assets for a specific network
def process_assets(chain_name, addresses, provider_url):
    for i in range(0, len(addresses), 2):
        atoken_address = addresses[i]
        underlying_token_address = addresses[i + 1]

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
