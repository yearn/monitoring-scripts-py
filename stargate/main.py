from web3 import Web3, constants
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()

provider_url_polygon = os.getenv("PROVIDER_URL")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")

with open("../common-abi/Strategy.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_strategy = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_strategy = abi_data

with open("../common-abi/ERC20.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_erc20 = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_erc20 = abi_data

polygon_addresses = [
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # usdc.e
    "0x8BBa7AFd0f9B1b664C161EC31d812a8Ec15f7e1a", # stargate staker usdc.e strategy
    "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", # usdt
    "0x2c5d0c3DB75D2f8A4957c74BE09194a9271Cf28D", # stargate staker usdt strategy
    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", # dai
    "0x06eD7C67755344548FAFe1822bEE365C4208a57F" # stargate staker dai strategy
    # Add more pairs as needed
]

arbitrum_addresses = [
    "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",  # usdc.e
    "0x2AE37f40235F3721DC78176dDBd100A12A8ce19C", # stargate staker usdc.e strategy
    "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", # usdt
    "0x5108DB0852C0CAA2Df797DcF31f8A73bFb335452" # stargate staker usdt strategy
    # Add more pairs as needed
]

buffer = 0.1

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")

def print_stuff(total_debt, net_room, total_idle, strategy_name, underlying_token_decimals, chain_name):

    total_debt /= 10**underlying_token_decimals
    net_room /= 10**underlying_token_decimals
    total_idle /= 10**underlying_token_decimals

    message = (
        "🚨 **DANGER** 🚨\n"
        f"🌟 Stargate withdraw room: {net_room:.3f}\n"
        f"💰 Total assets idle in strategy: {total_idle:.3f}\n"
        f"📈 Total assets deposited in stargate: {total_debt:.3f}\n"
        f"🔍 Strategy name: {strategy_name}\n"
        f"🌐 Chain: {chain_name}"
    )
    print(message)
    send_telegram_message(message)

# Build strategy or token
def build_token_or_strategy(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_strategy)
    return contract

# Function to process assets for a specific network
def process_assets(chain_name, addresses, provider_url):
    for i in range(0, len(addresses), 2):
        underlying_token_address = addresses[i]
        strategy_address = addresses[i + 1]

        # Build contracts
        underlying_token = build_token_or_strategy(underlying_token_address, provider_url)
        strategy = build_token_or_strategy(strategy_address, provider_url)

        # Get total supply and available balance
        withdraw_room = strategy.functions.availableWithdrawLimit(constants.ADDRESS_ZERO).call()
        total_idle = underlying_token.functions.balanceOf(strategy.address).call()
        net_room = withdraw_room - total_idle

        total_assets = strategy.functions.totalAssets().call()
        total_debt = total_assets - total_idle
    
        if (total_debt * (1 + buffer) > net_room):
            strategy_name = strategy.functions.name().call()
            underlying_token_decimals = strategy.functions.decimals().call()
            print_stuff(int(total_debt), int(net_room), int(total_idle), strategy_name, int(underlying_token_decimals), chain_name)
            
def main():
    print("Processing Polygon assets...")
    process_assets("Polygon", polygon_addresses, provider_url_polygon)

    print("Processing Arbitrum assets...")
    process_assets("Arbitrum", arbitrum_addresses, provider_url_arb)


if __name__ == "__main__":
    main()
