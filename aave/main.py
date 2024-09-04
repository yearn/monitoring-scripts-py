from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

provider_url_polygon = os.getenv("PROVIDER_URL")
provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")
provider_url_op = os.getenv("PROVIDER_URL_OPTIMISM")

with open("aave/abi/AToken.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_atoken = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_atoken = abi_data

polygon_addresses = [
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

mainnet_addresses = [
    "0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8", # aweth
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", # weth
    "0x23878914EFE38d27C4D67Ab83ed1b93A74D4086a", # ausdt
    "0xdAC17F958D2ee523a2206206994597C13D831ec7", # usdt
    "0x98C23E9d8f34FEFb1B7BD6a91B7FF122F4e16F5c", # ausdc
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", # usdc
    "0x018008bfb33d285247A21d44E50697654f754e63", # adai
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # dai
    "0xb82fa9f31612989525992FCfBB09AB22Eff5c85A", # acrvUSD
    "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E", # crvUSD
]

arbitrum_addresses = [
    "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8", # aweth
    "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", # weth
    "0x724dc807b04555b71ed48a6896b6F41593b8C637", # ausdc
    "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", # usdc
    "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE", # adai
    "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", # dai
    "0x625E7708f30cA75bfd92586e17077590C60eb4cD", # ausdc.e
    "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", # usdc.e
    "0x6ab707Aca953eDAeFBc4fD23bA73294241490620", # ausdt
    "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", # usdt
    "0x6533afac2E7BCCB20dca161449A13A32D391fb00", # aarb
    "0x912CE59144191C1204E64559FE8253a0e49E6548", # arb
]

optimism_addresses = [
    "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8", # aweth
    "0x4200000000000000000000000000000000000006", # weth
    "0x38d693cE1dF5AaDF7bC62595A37D667aD57922e5", # ausdc
    "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", # usdc
    "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE", # adai
    "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", # dai
    "0x625E7708f30cA75bfd92586e17077590C60eb4cD", # ausdc.e
    "0x7F5c764cBc14f9669B88837ca1490cCa17c31607", # usdc.e
    "0x6ab707Aca953eDAeFBc4fD23bA73294241490620", # ausdt
    "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58", # usdt
    "0x513c7E3a9c69cA3e22550eF58AC1C0088e918FFf", # aop
    "0x4200000000000000000000000000000000000042", # op
]

# TODO: Add different threshold UR's for each asset
THRESHOLD_UR = 0.93
THRESHOLD_UR_NOTIFICATION = 0.99

# Build contract function
def build_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_atoken)
    return contract

def send_telegram_message(message, disable_notification):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_AAVE")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_AAVE")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message, "disable_notification": disable_notification}
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
        disable_notification = True
        if ur > THRESHOLD_UR_NOTIFICATION:
            disable_notification = False
        print(message)
        send_telegram_message(message, disable_notification)

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
