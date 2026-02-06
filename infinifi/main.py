import requests
from web3 import Web3

from utils.abi import load_abi
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

# Constants
PROTOCOL = "infinifi"
logger = get_logger(PROTOCOL)
IUSD_ADDRESS = Web3.to_checksum_address("0x48f9e38f3070AD8945DFEae3FA70987722E3D89c")
LIQUID_RESERVES_THRESHOLD = 15_000_000

# API Configuration
API_BASE_URL = "https://api.infinifi.xyz"
API_PROTOCOL_DATA = "/api/protocol/data"


def fetch_api_data():
    """Fetches data from the Infinifi API."""
    url = f"{API_BASE_URL}{API_PROTOCOL_DATA}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("API Error %s for %s: %s", response.status_code, url, response.text[:200])
            return None
    except Exception as e:
        logger.error("API Request Failed for %s: %s", url, e)
        return None


def main():
    client = ChainManager.get_client(Chain.MAINNET)
    erc20_abi = load_abi("common-abi/ERC20.json")

    iusd_contract = client.get_contract(IUSD_ADDRESS, erc20_abi)

    try:
        # --- 1. iUSD Supply ---
        # Batch calls for decimals and totalSupply
        with client.batch_requests() as batch:
            batch.add(iusd_contract.functions.decimals())
            batch.add(iusd_contract.functions.totalSupply())

            batch_results = client.execute_batch(batch)

        iusd_decimals = int(batch_results[0])
        iusd_supply_raw = int(batch_results[1])

        iusd_supply = iusd_supply_raw / (10**iusd_decimals)

        # --- 2. Fetch API Data ---
        liquid_reserves = 0
        total_backing = 0
        api_data = fetch_api_data()

        if not api_data:
            logger.warning("No API data received.")
        elif api_data.get("code") != "OK" or "data" not in api_data:
            logger.warning("API Data format unexpected. Code: %s", api_data.get("code"))
        else:
            stats = api_data["data"]["stats"]
            # Extract Liquid Reserves & TVL (using 'asset' key for USDC)
            asset_stats = stats.get("asset")

            if asset_stats:
                if "totalLiquidAssetNormalized" in asset_stats:
                    liquid_reserves = float(asset_stats["totalLiquidAssetNormalized"])

                if "totalTVLAssetNormalized" in asset_stats:
                    total_backing = float(asset_stats["totalTVLAssetNormalized"])

        logger.info("--- Infinifi Stats ---")
        logger.info("iUSD Supply:     $%s", f"{iusd_supply:,.2f}")

        if liquid_reserves > 0:
            logger.info("Liquid Reserves: $%s", f"{liquid_reserves:,.2f}")
        else:
            logger.info("Liquid Reserves: [Data Not Available]")

        if total_backing > 0:
            logger.info("Total Backing:   $%s", f"{total_backing:,.2f}")
            # Calculate strategy assets implied if not fetched directly
            implied_strategies = total_backing - liquid_reserves
            if implied_strategies > 0:
                logger.info("Implied Strategy Assets: $%s", f"{implied_strategies:,.2f}")
        else:
            logger.info("Total Backing:   [Data Not Available]")

        # --- Alerts ---

        # Alert 1: Low Liquid Reserves
        # Check against a threshold ($25M)
        if liquid_reserves > 0:
            cache_key_reserves = f"{PROTOCOL}_liquid_reserves"
            last_reserves = float(get_last_value_for_key_from_file(cache_filename, cache_key_reserves))

            if (
                last_reserves != 0
                and liquid_reserves < LIQUID_RESERVES_THRESHOLD
                and last_reserves >= LIQUID_RESERVES_THRESHOLD
            ):
                msg = f"📉 *Infinifi Liquid Reserves Alert*\n\nReserves dropped below ${LIQUID_RESERVES_THRESHOLD:,.0f}: ${liquid_reserves:,.2f}"
                send_telegram_message(msg, PROTOCOL)

            write_last_value_to_file(cache_filename, cache_key_reserves, liquid_reserves)

    except Exception as e:
        logger.error("Error: %s", e)
        send_telegram_message(f"⚠️ Infinifi monitoring failed: {e}", PROTOCOL, False, True)


if __name__ == "__main__":
    main()
