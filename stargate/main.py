from web3 import Web3, constants
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()

provider_url = os.getenv("PROVIDER_URL")
w3 = Web3(Web3.HTTPProvider(provider_url))

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

with open("./abi/StargatePool.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_stg_pool = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_stg_pool = abi_data

stargate_pool = w3.eth.contract(address="0x1205f31718499dBf1fCa446663B532Ef87481fe1", abi=abi_stg_pool) # Polygon USDC Pool
strategy = w3.eth.contract(address="0x8BBa7AFd0f9B1b664C161EC31d812a8Ec15f7e1a", abi=abi_strategy) # Polygon USDC Stargate Staker
usdc = w3.eth.contract(address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", abi=abi_erc20) # Polygon USDC.E

buffer = 0.1

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")

def print_stuff(total_debt, net_room, total_idle, strategy_name):
    message = (
        "🚨 **DANGER** 🚨\n"
        f"🌟 Stargate withdraw room: {net_room}\n"
        f"💰 Total assets idle in strategy: {total_idle}\n"
        f"📈 Total assets deposited in stargate: {total_debt}\n"
        f"🔍 Strategy name: {strategy_name}"
    )
    print(message)
    send_telegram_message(message)
    
def main():
    res = stargate_pool.functions.deltaCredit().call()

    withdraw_room = strategy.functions.availableWithdrawLimit(constants.ADDRESS_ZERO).call()
    total_idle = usdc.functions.balanceOf(strategy.address).call()
    net_room = withdraw_room - total_idle

    total_assets = strategy.functions.totalAssets().call()
    total_debt = total_assets - total_idle
    
    if (total_debt * (1 + buffer) > net_room):
        status = 0
        strategy_name = strategy.functions.name().call()
        print_stuff(total_debt, net_room, total_idle, strategy_name)


if __name__ == "__main__":
    main()
