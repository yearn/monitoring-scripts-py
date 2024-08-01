from web3 import Web3, constants
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()

provider_url = os.getenv("PROVIDER_URL")
w3 = Web3(Web3.HTTPProvider(provider_url))

with open("./abi/AToken.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_atoken = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_atoken = abi_data

lending_pool_address = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
addresses = [
    "0x1a13F4Ca1d028320A707D99520AbFefca3998b7F",  # ausdc.e 
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # usdc.e
    "0xA4D94019934D8333Ef880ABFFbF2FDd611C762BD", # ausdc
    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", # usdc
    "0x6ab707Aca953eDAeFBc4fD23bA73294241490620", # ausdt
    "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", # usdt
    "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE", # adai
    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", # dai
    "0x6d80113e533a2C0fe82EaBD35f1875DcEA89Ea97", # amatic
    "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", # matic
    "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8", # aweth
    "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619" # weth
    # Add more pairs as needed
]

# TODO: Add different threshold UR's for each asset
THREHSOLD_UR = 0.95

# Build contract function
def build_contract(address):
    contract = w3.eth.contract(address=address, abi=abi_atoken) # Polygon USDC Pool
    return contract

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_AAVE")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_AAVE")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")

def print_stuff(token_name, ur):
    # maybe only print if UR is somewhere? like ur >= .95 ?

    if (ur > THREHSOLD_UR):
        message = (
        "🚨 **BEEP BOP** 🚨\n"
        f"💎 Market asset: {token_name}\n"
        f"📊 Utilization rate: {ur:.2%}"
        )
        print(message)
        send_telegram_message(message)


# Main function
def main():
    # Iterate over the addresses list in pairs
    for i in range(0, len(addresses), 2):
        atoken_address = addresses[i]
        underlying_token_address = addresses[i + 1]

        # Build contracts
        atoken = build_contract(atoken_address)
        underlying_token = build_contract(underlying_token_address)

        # Get total supply and available balance
        ts = atoken.functions.totalSupply().call()
        av = underlying_token.functions.balanceOf(atoken_address).call()

        # Calculate debt and utilization rate
        debt = ts - av
        ur = debt / ts if ts != 0 else 0

        token_name = underlying_token.functions.symbol().call()
        print_stuff(token_name, ur)

# Run the main function
if __name__ == "__main__":
    main()


    