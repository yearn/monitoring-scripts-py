import json
import os

from utils.cache import get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "RTOKEN"
COVERAGE_THRESHOLD = 1.04
ETH_REDEMPTION_THRESHOLD = 5000e18  # 50% of normal redemption amount

# Contract Addresses
RTOKEN_ADDRESS = "0xE72B141DF173b999AE7c1aDcbF60Cc9833Ce56a8"
STRSR_ADDRESS = "0xffa151Ad0A0e2e40F39f9e5E9F87cF9E45e819dd"

# NOTE: change cache key to addresses if more than one rtoken is monitored
STRSR_RATE_CACHE_KEY = "rtoken+strsr+rate"
CACHE_FILENAME = os.getenv("CACHE_FILENAME", "cache-id.txt")


# Load ABI files
def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


ABI_RTOKEN = load_abi("rtoken/abi/rtoken.json")
ABI_STRSR = load_abi("rtoken/abi/strsr.json")


def main():
    client = ChainManager.get_client(Chain.MAINNET)

    try:
        rtoken = client.eth.contract(address=RTOKEN_ADDRESS, abi=ABI_RTOKEN)
        strsr = client.eth.contract(address=STRSR_ADDRESS, abi=ABI_STRSR)
    except Exception as e:
        error_message = f"Error creating contract instances: {e}. Check ABI paths and contract addresses."
        print(error_message)
        return  # Cannot proceed without contracts

    basket_needed = None
    total_supply = None
    current_rate = None
    redemption_available = None
    # --- Combined Blockchain Calls ---
    try:
        with client.batch_requests() as batch:
            # Add RToken calls
            batch.add(rtoken.functions.basketsNeeded())
            batch.add(rtoken.functions.totalSupply())
            batch.add(rtoken.functions.redemptionAvailable())
            # Add StRSR call
            batch.add(strsr.functions.exchangeRate())

            responses = client.execute_batch(batch)

            if len(responses) == 4:
                basket_needed, total_supply, redemption_available, current_rate = responses
                print(
                    f"Raw Data - Basket Needed: {basket_needed}, Total Supply: {total_supply}, Redemption Available: {redemption_available}, StRSR Rate: {current_rate}"
                )

                # Validate response types
                if not isinstance(basket_needed, int) or not isinstance(total_supply, int):
                    print(
                        f"Warning: Received non-integer values from RToken contract. Basket: {basket_needed}, Supply: {total_supply}"
                    )
                    basket_needed = None  # Invalidate for coverage check
                    total_supply = None
                if not isinstance(redemption_available, int):
                    print(
                        f"Warning: Received non-integer value from RToken contract redemptionAvailable: {redemption_available}"
                    )
                    redemption_available = None  # Invalidate for coverage check
                if not isinstance(current_rate, int):
                    print(f"Warning: Received non-integer value from StRSR contract exchangeRate: {current_rate}")
                    current_rate = None  # Invalidate for rate check

            else:
                error_message = f"Batch Call: Expected 3 responses, got {len(responses)}"
                print(error_message)
                send_telegram_message(error_message, PROTOCOL)
                return  # Cannot proceed without expected data

    except Exception as e:
        error_message = f"Error during batch blockchain calls: {e}"
        print(error_message)
        send_telegram_message(error_message, PROTOCOL)
        return  # Cannot proceed if batch fails

    # --- RToken Coverage Check (using fetched data) ---
    if basket_needed is not None and total_supply is not None:
        if total_supply == 0:  # Basket needed should be positive
            send_telegram_message("⚠️ Warning: totalSupply is zero.", PROTOCOL)
        else:
            coverage = basket_needed / total_supply
            print(f"RToken Coverage: {coverage:.4f}")
            if coverage < COVERAGE_THRESHOLD:
                message = (
                    f"🚨 *{PROTOCOL} Alert* 🚨\\n"
                    f"RToken coverage below threshold!\\n"
                    f"Current Coverage: {coverage:.4f}\\n"
                    f"Threshold: {COVERAGE_THRESHOLD:.2f}\\n"
                    f"Total Supply: {total_supply / 1e18:.4f}\\n"
                    f"Basket Needed: {basket_needed / 1e18:.4f}"
                )
                send_telegram_message(message, PROTOCOL)
    else:
        send_telegram_message("Skipping RToken coverage check due to invalid data from batch.", PROTOCOL)

    # --- RToken Redemption Available Check (using fetched data) ---
    if redemption_available is not None:
        print(f"RToken Redemption Available: {redemption_available}")
        if redemption_available < ETH_REDEMPTION_THRESHOLD:
            print("⚠️ Warning: redemptionAvailable is less than 1k ETH.")
            message = (
                f"🚨 *{PROTOCOL} Alert* 🚨\\n"
                f"RToken redemptionAvailable is less than 1k ETH!\\n"
                f"Redemption Available: {redemption_available / 1e18:.4f} ETH\\n"
                f"Threshold: {ETH_REDEMPTION_THRESHOLD / 1e18:.4f} ETH\\n"
            )
            send_telegram_message(message, PROTOCOL)
    else:
        send_telegram_message("Skipping RToken redemptionAvailable check due to invalid data from batch.", PROTOCOL)

    # --- StRSR Exchange Rate Check (using fetched data and cache) ---
    if current_rate is not None:
        try:
            print(f"StRSR Current Exchange Rate: {current_rate}")
            initial_rate = get_last_value_for_key_from_file(CACHE_FILENAME, STRSR_RATE_CACHE_KEY)

            if initial_rate == 0:
                # skip sending alert if initial rate is not set
                print(f"Saving initial StRSR exchange rate to cache: {current_rate}")
            elif current_rate < initial_rate:
                message = (
                    f"🚨 *{PROTOCOL} Alert* 🚨\\n"
                    f"StRSR exchange rate dropped below initial value!\\n"
                    f"Current Rate: {current_rate}\\n"
                    f"Initial Rate (from cache): {initial_rate}"
                )
                send_telegram_message(message, PROTOCOL)

            write_last_value_to_file(CACHE_FILENAME, STRSR_RATE_CACHE_KEY, current_rate)

        except Exception as e:
            error_message = f"Error processing StRSR exchange rate with cache: {e}"
            print(error_message)
    else:
        send_telegram_message("Skipping StRSR exchange rate check due to invalid data from batch.", PROTOCOL)


if __name__ == "__main__":
    main()
