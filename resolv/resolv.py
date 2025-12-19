import time
from datetime import datetime

from utils.abi import load_abi
from utils.cache import (
    cache_filename,
    get_last_value_for_key_from_file,
    write_last_value_to_file,
)
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "RESOLV"

USR_PRICE_STORAGE = "0x7f45180d6fFd0435D8dD695fd01320E6999c261c"
USR_REDEMPTION = "0x60A7B7915980ed34fDE6e239618fAdCf67897c37"

ABI_USR_PRICE_STORAGE = load_abi("resolv/abi/usr_price_storage.json")
ABI_USR_REDEMPTION = load_abi("resolv/abi/usr_redemption.json")


def get_redemption_cache() -> tuple[int | None, int | None]:
    """Returns (usage, last_reset_time) or (None, None) if no cache"""
    cache_data = get_last_value_for_key_from_file(cache_filename, PROTOCOL)
    if cache_data == 0:
        return None, None

    parts = str(cache_data).split("|")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])


def write_redemption_cache(usage: int, reset_time: int) -> None:
    """Write redemption cache data using existing cache system"""
    cache_value = f"{usage}|{reset_time}"
    write_last_value_to_file(cache_filename, PROTOCOL, cache_value)


def should_alert_redemption(current_usage: int, redemption_limit: int) -> bool:
    """
    Smart caching logic that only writes to cache when necessary:
    - On first run
    - When reset is detected
    - When threshold is crossed (alert triggered)
    - When 24+ hours have passed since last reset and data is still over threshold
    """
    cached_usage, last_reset_time = get_redemption_cache()
    current_time = int(time.time())
    threshold = redemption_limit / 2

    # First run - save cache and check threshold
    if cached_usage is None:
        write_redemption_cache(current_usage, current_time)
        return current_usage > threshold

    # Detect reset: current usage < cached usage indicates 24h reset happened
    reset_detected = current_usage < cached_usage

    if reset_detected:
        # Reset detected - save new state and check threshold
        write_redemption_cache(current_usage, current_time)
        return current_usage > threshold

    # Check if threshold crossed since last cache
    threshold_crossed = (cached_usage <= threshold) and (current_usage > threshold)

    if threshold_crossed:
        # Threshold crossed - save cache and alert
        write_redemption_cache(current_usage, last_reset_time)
        return True

    # Time-based alert: if above threshold and 24+ hours since last reset
    time_since_reset = current_time - last_reset_time
    still_above_threshold = current_usage > threshold
    twenty_four_hours = 24 * 60 * 60

    if still_above_threshold and time_since_reset >= twenty_four_hours:
        # Update reset time to prevent spam (alert once per 24h period)
        print("Data over threshold for 24+ hours")
        write_redemption_cache(current_usage, current_time)
        return True

    # No significant change - don't save cache, just continue monitoring
    print(
        f"Cached usage: {cached_usage}, Last reset time: {last_reset_time}, Current usage: {current_usage}, Threshold: {threshold}"
    )
    return False


def main() -> None:
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
                send_telegram_message(error_message, PROTOCOL, True, True)
                return  # Cannot proceed without expected data

    except Exception as e:
        error_message = f"Error during batch blockchain calls: {e}"
        send_telegram_message(error_message, PROTOCOL, True, True)
        return  # Cannot proceed if batch fails

    (usr_price, usr_supply, reserves, timestamp) = usr_last_price

    error_messages = []

    if usr_price != 1e18:
        message = (
            f"USR Price is not 1e18!\n"
            f"USR Price: {usr_price / 1e18:.4f}\n"
            f"USR Supply: {usr_supply / 1e18:.4f}\n"
            f"Reserves: {reserves / 1e18:.4f}\n"
            f"Timestamp: {timestamp}"
        )
        error_messages.append(message)

    if usr_supply > reserves * 1.3:
        message = (
            f"USR Supply is greater than 130% of Reserves!\n"
            f"USR Supply: {usr_supply / 1e18:.4f}\n"
            f"Reserves: {reserves / 1e18:.4f}"
        )
        error_messages.append(message)

    if should_alert_redemption(current_redemption_usage, redemption_limit):
        message = (
            f"Current Redemption Usage is greater than 50% of Redemption Limit!\n"
            f"Current Redemption Usage: {current_redemption_usage / 1e18:.4f}\n"
            f"Redemption Limit: {redemption_limit / 1e18:.4f}\n"
            f"Available redemption: {(redemption_limit - current_redemption_usage) / 1e18:.4f}"
        )
        error_messages.append(message)

    # Check if timestamp is older than one day
    current_time = int(time.time())
    one_day_ago = current_time - (24 * 60 * 60)  # 24 hours in seconds
    if timestamp < one_day_ago:
        message = (
            f"⚠️ USR data is stale!\n"
            f"Last update: {datetime.fromtimestamp(timestamp)}\n"
            f"Current time: {datetime.fromtimestamp(current_time)}"
        )
        error_messages.append(message)

    if error_messages:
        send_telegram_message("\n".join(error_messages), PROTOCOL)


if __name__ == "__main__":
    main()
