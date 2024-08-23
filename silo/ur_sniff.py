from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")

with open("./abi/SiloLens.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_sl = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_sl = abi_data

arbitrum_addresses_usdce = [
    "0xA8897b4552c075e884BDB8e7b704eB10DB29BF0D", # first is silo
    "Silo WSTETH-USDC.e", # second is name
    "0x69eC552BE56E6505703f0C861c40039e5702037A",
    "Silo WBTC-USDC.e",
]
arbitrum_silo_lens_address = "0xBDb843c7a7e48Dc543424474d7Aa63b61B5D9536"
arbitrum_usdce_address = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"

# TODO: Add different threshold UR's for each asset
THRESHOLD_UR = 0.90

# Build contract function
def build_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_sl)
    return contract

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_SILO")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_SILO")
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
def process_assets(chain_name, values, silo_lens_address, quote_address, provider_url):
    silo_lens = build_contract(silo_lens_address, provider_url)
    for i in range(0, len(values), 2):
        silo_address = values[i] # first is silo address
        silo_name = values[i + 1] # second is name of silo

        ur = silo_lens.functions.getUtilization(silo_address, quote_address).call()
        human_readable_ur = (ur / 1e18)
        print_stuff(chain_name, silo_name, human_readable_ur)

# Main function
def main():
    print("Processing Arbitrum USDC.E Silos...")
    process_assets("Arbitrum", arbitrum_addresses_usdce, arbitrum_silo_lens_address, arbitrum_usdce_address, provider_url_arb)

# Run the main function
if __name__ == "__main__":
    main()
