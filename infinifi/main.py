import os
import requests
from web3 import Web3
from dotenv import load_dotenv

from utils.abi import load_abi
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

load_dotenv()

# Constants
PROTOCOL = "infinifi"
IUSD_ADDRESS = Web3.to_checksum_address("0x48f9e38f3070AD8945DFEae3FA70987722E3D89c")
USDC_ADDRESS = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")

# API Configuration
API_BASE_URL = "https://api.infinifi.xyz"
API_PROTOCOL_DATA = "/api/protocol/data"

# TODO: Fill in these addresses with actual Mainnet addresses if API is not used
# Address holding the liquid USDC reserves
LIQUID_RESERVE_WALLET = None  # e.g. Web3.to_checksum_address("...")
# Addresses of strategy vaults/contracts to sum up assets
STRATEGY_ADDRESSES = [
    # Web3.to_checksum_address("..."),
]


def fetch_api_data(endpoint):
    """Fetches data from the Infinifi API."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        # User-Agent to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error {response.status_code} for {url}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"API Request Failed for {url}: {e}")
        return None


def get_strategy_assets_onchain(client, erc20_abi):
    """
    Calculates total assets in strategies using on-chain calls.
    """
    total_assets = 0
    if not STRATEGY_ADDRESSES:
        return 0

    for address in STRATEGY_ADDRESSES:
        try:
            # Placeholder: Assuming strategies report totalAssets() or similar
            # contract = client.get_contract(address, strategy_abi)
            # total_assets += contract.functions.totalAssets().call() / 1e6
            pass
        except Exception as e:
            print(f"Error reading strategy {address}: {e}")

    return total_assets


def main():
    client = ChainManager.get_client(Chain.MAINNET)
    erc20_abi = load_abi("common-abi/ERC20.json")

    iusd_contract = client.get_contract(IUSD_ADDRESS, erc20_abi)
    usdc_contract = client.get_contract(USDC_ADDRESS, erc20_abi)

    try:
        # --- 1. iUSD Supply ---
        # Dynamically get decimals
        iusd_decimals = iusd_contract.functions.decimals().call()
        iusd_supply_raw = iusd_contract.functions.totalSupply().call()
        iusd_supply = iusd_supply_raw / (10**iusd_decimals)

        # --- 2. Fetch API Data ---
        liquid_reserves = 0
        total_backing = 0
        api_data = fetch_api_data(API_PROTOCOL_DATA)

        if api_data:
            if api_data.get("code") == "OK" and "data" in api_data:
                stats = api_data["data"]["stats"]
                
                # Extract Liquid Reserves (using 'asset' key for USDC)
                if "asset" in stats and "totalLiquidAssetNormalized" in stats["asset"]:
                    liquid_reserves = float(stats["asset"]["totalLiquidAssetNormalized"])

                # Extract Total Backing (TVL)
                if "asset" in stats and "totalTVLAssetNormalized" in stats["asset"]:
                    total_backing = float(stats["asset"]["totalTVLAssetNormalized"])
            else:
                print(f"API Data format unexpected. Code: {api_data.get('code')}")
        else:
            print("No API data received.")

        # Fallback to on-chain if API failed for components
        if liquid_reserves == 0 and LIQUID_RESERVE_WALLET:
            reserves_raw = usdc_contract.functions.balanceOf(LIQUID_RESERVE_WALLET).call()
            liquid_reserves = reserves_raw / 1e6  # USDC is 6 decimals
            print("Fetched Liquid Reserves from On-Chain (Fallback).")

        if total_backing == 0:
            strategy_assets = get_strategy_assets_onchain(client, erc20_abi)
            if strategy_assets > 0:
                 total_backing = liquid_reserves + strategy_assets
                 print("Calculated Total Backing from On-Chain (Fallback).")

        print("\n--- Infinifi Stats ---")
        print(f"iUSD Supply:     ${iusd_supply:,.2f}")
        
        if liquid_reserves > 0:
            print(f"Liquid Reserves: ${liquid_reserves:,.2f}")
        else:
            print("Liquid Reserves: [Data Not Available]")

        if total_backing > 0:
            print(f"Total Backing:   ${total_backing:,.2f}")
            # Calculate strategy assets implied if not fetched directly
            implied_strategies = total_backing - liquid_reserves
            if implied_strategies > 0:
                print(f"Implied Strategy Assets: ${implied_strategies:,.2f}")
        else:
            print("Total Backing:   [Data Not Available]")

        # --- Alerts ---

        # Alert 1: Low Liquid Reserves
        # Check against a threshold (e.g., $30M, current is ~$34.9M)
        if liquid_reserves > 0:
            cache_key_reserves = f"{PROTOCOL}_liquid_reserves"
            last_reserves = float(get_last_value_for_key_from_file(cache_filename, cache_key_reserves))

            threshold = 30_000_000

            if last_reserves != 0 and liquid_reserves < threshold and last_reserves >= threshold:
                msg = f"📉 *Infinifi Liquid Reserves Alert*\n\nReserves dropped below ${threshold:,.0f}: ${liquid_reserves:,.2f}"
                send_telegram_message(msg, PROTOCOL)

            write_last_value_to_file(cache_filename, cache_key_reserves, liquid_reserves)

        # Alert 2: Backing Health
        if total_backing > 0:
            if total_backing < iusd_supply:
                msg = f"⚠️ *Infinifi Undercollateralized*\n\nSupply: ${iusd_supply:,.2f}\nBacking: ${total_backing:,.2f}"
                # Simple alert logic - could be refined to avoid spam
                # send_telegram_message(msg, PROTOCOL)
                pass

    except Exception as e:
        print(f"Error: {e}")
        send_telegram_message(f"⚠️ Infinifi monitoring failed: {e}", PROTOCOL, False, True)


if __name__ == "__main__":
    main()
