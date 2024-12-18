from web3 import Web3
from dotenv import load_dotenv
import os, json, requests
from utils.telegram import send_telegram_message

load_dotenv()

# TODO: Add different threshold UR's for each asset
THRESHOLD_UR = 0.94
THRESHOLD_UR_NOTIFICATION = 0.98
PROTOCOL = "SILO"

provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")

with open("silo/abi/SiloLens.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_sl = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_sl = abi_data

arbitrum_addresses_usdce = [
    ["Silo WSTETH-USDC.e", "0xA8897b4552c075e884BDB8e7b704eB10DB29BF0D"],
    ["Silo WBTC-USDC.e", "0x69eC552BE56E6505703f0C861c40039e5702037A"],
    ["Silo ARB-USDC.E", "0x0696E6808EE11a5750733a3d821F9bB847E584FB"],
]
arbitrum_silo_lens_address = "0xBDb843c7a7e48Dc543424474d7Aa63b61B5D9536"
arbitrum_usdce_address = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"


def print_stuff(chain_name, token_name, ur):
    print(f"Chain: {chain_name}, Token: {token_name}, UR: {ur}")
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
def process_assets(chain_name, values, silo_lens_address, quote_address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    silo_lens = w3.eth.contract(address=silo_lens_address, abi=abi_sl)

    # Prepare batch calls
    with w3.batch_requests() as batch:
        # Add all utilization calls to the batch
        calls = []
        for silo_name, silo_address in values:
            calls.append(
                (
                    silo_name,
                    batch.add(
                        silo_lens.functions.getUtilization(silo_address, quote_address)
                    ),
                )
            )

        # Execute all calls at once
        responses = batch.execute()
        if len(responses) != len(values):
            raise ValueError(
                f"Expected {len(values)} responses from batch, got: {len(responses)}"
            )

        # Process results
        for (silo_name, _), ur in zip(values, responses):
            human_readable_ur = ur / 1e18
            print_stuff(chain_name, silo_name, human_readable_ur)


# Main function
def main():
    print("Processing Arbitrum USDC.E Silos...")
    process_assets(
        "Arbitrum",
        arbitrum_addresses_usdce,
        arbitrum_silo_lens_address,
        arbitrum_usdce_address,
        provider_url_arb,
    )


# Run the main function
if __name__ == "__main__":
    main()
