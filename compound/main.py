from web3 import Web3
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message

load_dotenv()

PROTOCOL = "comp"
THRESHOLD_UR = 0.99
THRESHOLD_UR_NOTIFICATION = 0.99

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


def process_assets(chain_name, addresses, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))

    # Prepare batch calls
    with w3.batch_requests() as batch:
        contracts = []
        for i in range(0, len(addresses), 2):
            ctoken_address = addresses[i]
            ctoken = w3.eth.contract(address=ctoken_address, abi=abi_ctoken)
            contracts.append(ctoken)

            # Add utilization call to batch
            batch.add(ctoken.functions.getUtilization())

        # Execute all calls at once
        responses = batch.execute()
        expected_responses = len(addresses) / 2  # 1 call per token pair
        if len(responses) != expected_responses:
            raise ValueError(
                f"Expected {expected_responses} responses from batch, got: {len(responses)}"
            )

    # Process results
    for i in range(len(responses)):
        ur = int(responses[i]) / 1e18  # unscale it
        ctoken_name = addresses[i * 2 + 1]  # get token name from addresses array
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
