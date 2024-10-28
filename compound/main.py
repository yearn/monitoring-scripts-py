from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

provider_url_polygon = os.getenv("PROVIDER_URL")
provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")
provider_url_op = os.getenv("PROVIDER_URL_OPTIMISM")

with open("compound/abi/CTokenV3.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_ctoken = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_ctoken = abi_data

polygon_addresses = [
    "0xF25212E676D1F7F89Cd72fFEe66158f541246445",
    "cUSDC.Ev3",
    "0xaeB318360f27748Acb200CE616E389A6C9409a07",
    "cUSDTv3",
    # Add more pairs as needed
]

mainnet_addresses = [
    "0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840",
    "cUSDTv3",
    "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
    "cUSDCv3",
    "0xA17581A9E3356d9A858b789D68B4d866e593aE94",
    "cWETHv3",
    # Add more pairs as needed
]

arbitrum_addresses = [
    "0xd98Be00b5D27fc98112BdE293e487f8D4cA57d07",
    "cUSDTv3",
    "0x6f7D514bbD4aFf3BcD1140B7344b32f063dEe486",
    "cWETHv3",
    "0xA5EDBDD9646f8dFF606d7448e414884C7d905dCA",
    "cUSDC.Ev3",
    "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf",
    "cUSDCv3",
    # Add more pairs as needed
]

optimism_addresses = [
    "0x2e44e174f7D53F0212823acC11C01A11d58c5bCB",
    "cUSDCv3",
    "0x995E394b8B2437aC8Ce61Ee0bC610D617962B214",
    "cUSDTv3",
    "0xE36A30D249f7761327fd973001A32010b521b6Fd",
    "cWETHv3",
    # Add more pairs as needed
]


# Build contract function
def build_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_ctoken)
    return contract


def send_telegram_message(message, disable_notification):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_COMP")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_COMP")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
        "disable_notification": disable_notification,
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(
            f"Failed to send telegram message: {response.status_code} - {response.text}"
        )


THRESHOLD_UR = 0.96
THRESHOLD_UR_NOTIFICATION = 0.99


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
        print(message)
        send_telegram_message(message, disable_notification)


def process_assets(chain_name, addresses, provider_url):
    for i in range(0, len(addresses), 2):
        ctoken = build_contract(addresses[i], provider_url)
        ctoken_name = addresses[i + 1]
        ur = int(ctoken.functions.getUtilization().call())
        ur = ur / 1e18  # unscale it, it will be some number like 0.7, 0.8
        print_stuff(chain_name, ctoken_name, ur)


# Main function
def main():
    print("Processing Polygon assets...")
    process_assets("Polygon", polygon_addresses, provider_url_polygon)

    print("Processing Mainnet assets...")
    process_assets("Mainnet", mainnet_addresses, provider_url_mainnet)

    print("Processing Arbitrum assets...")
    process_assets("Arbitrum", arbitrum_addresses, provider_url_arb)

    print("Processing Optimism assets...")
    process_assets("Optimism", optimism_addresses, provider_url_op)


# Run the main function
if __name__ == "__main__":
    main()
