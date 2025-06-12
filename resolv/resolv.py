import time
from datetime import datetime

from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager
from utils.abi import load_abi

PROTOCOL = "RESOLV"

USR_PRICE_STORAGE = "0x7f45180d6fFd0435D8dD695fd01320E6999c261c"
USR_REDEMPTION = "0x60A7B7915980ed34fDE6e239618fAdCf67897c37"

ABI_USR_PRICE_STORAGE = load_abi("resolv/abi/usr_price_storage.json")
ABI_USR_REDEMPTION = load_abi("resolv/abi/usr_redemption.json")


def main():
    client = ChainManager.get_client(Chain.MAINNET)

    try:
        usr_price_storage = client.eth.contract(address=USR_PRICE_STORAGE, abi=ABI_USR_PRICE_STORAGE)
        usr_redemption = client.eth.contract(address=USR_REDEMPTION, abi=ABI_USR_REDEMPTION)
    except Exception as e:
        error_message = f"Error creating contract instances: {e}. Check ABI paths and contract addresses."
        print(error_message)
        return  # Cannot proceed without contracts

    usr_last_price = None
    usr_price = None
    usr_supply = None
    reserves = None
    timestamp = None
    redemption_limit = None
    current_redemption_usage = None
    # --- Combined Blockchain Calls ---
    try:
        with client.batch_requests() as batch:
            batch.add(usr_redemption.functions.redemptionLimit())
            batch.add(usr_redemption.functions.currentRedemptionUsage())
            batch.add(usr_price_storage.functions.lastPrice())

            responses = client.execute_batch(batch)

            if len(responses) == 3:
                redemption_limit, current_redemption_usage, usr_last_price = responses
                print(
                    f"Raw Data - Redemption Limit: {redemption_limit}, Current Redemption Usage: {current_redemption_usage}, USR Last Price: {usr_last_price}"
                )
            else:
                error_message = f"Batch Call: Expected 3 responses, got {len(responses)}"
                print(error_message)
                send_telegram_message(error_message, PROTOCOL)
                return  # Cannot proceed without expected data

    except Exception as e:
        error_message = f"Error during batch blockchain calls: {e}"
        send_telegram_message(error_message, PROTOCOL)
        return  # Cannot proceed if batch fails

    (usr_price, usr_supply, reserves, timestamp) = usr_last_price

    if usr_price != 1e18:
        message = (
            f"🚨 *{PROTOCOL} Alert* 🚨\\n"
            f"USR Price is not 1e18!\\n"
            f"USR Price: {usr_price / 1e18:.4f}\\n"
            f"USR Supply: {usr_supply / 1e18:.4f}\\n"
            f"Reserves: {reserves / 1e18:.4f}\\n"
            f"Timestamp: {timestamp}"
        )
        send_telegram_message(message, PROTOCOL)

    if usr_supply > reserves * 1.3:
        message = (
            f"🚨 *{PROTOCOL} Alert* 🚨\\n"
            f"USR Supply is greater than 130% of Reserves!\\n"
            f"USR Supply: {usr_supply / 1e18:.4f}\\n"
            f"Reserves: {reserves / 1e18:.4f}\\n"
        )
        send_telegram_message(message, PROTOCOL)

    if current_redemption_usage > redemption_limit / 2:
        message = (
            f"🚨 *{PROTOCOL} Alert* 🚨\\n"
            f"Current Redemption Usage is greater than 50% of Redemption Limit!\\n"
            f"Current Redemption Usage: {current_redemption_usage / 1e18:.4f}\\n"
            f"Redemption Limit: {redemption_limit / 1e18:.4f}"
        )
        send_telegram_message(message, PROTOCOL)

    # Check if timestamp is older than one day
    current_time = int(time.time())
    one_day_ago = current_time - (24 * 60 * 60)  # 24 hours in seconds
    if timestamp < one_day_ago:
        message = (
            f"⚠️ USR data is stale!\n"
            f"Last update: {datetime.fromtimestamp(timestamp)}\n"
            f"Current time: {datetime.fromtimestamp(current_time)}"
        )
        send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    main()
