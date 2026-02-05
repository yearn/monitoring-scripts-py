import os
import re
import time
from datetime import datetime, timedelta

import requests

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

RESOLV_RESERVES_URL = "https://info.apostro.xyz/resolv-reserves"
REQUEST_TIMEOUT = 15

USR_OVER_COLLATERALIZATION_MIN_PCT = 130.0
MARKET_DELTA_ABS_PCT_TRIGGER = 3.0
NET_EXPOSURE_TVL_RATIO_TRIGGER = 0.03
RESERVES_DATA_MAX_AGE_HOURS = 6
ONE_DAY_SECONDS = 24 * 60 * 60
WEI_PER_ETHER = 1e18

TVL_CHANGE_RATIO_TRIGGER = 0.1
USR_TVL_CHANGE_RATIO_TRIGGER = 0.1
RLP_TVL_CHANGE_RATIO_TRIGGER = 0.1
BACKING_ASSETS_CHANGE_RATIO_TRIGGER = 0.05
RLP_USR_RATIO_PCT_CHANGE_TRIGGER = 5.0


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
    if current_usage > threshold and time_since_reset >= ONE_DAY_SECONDS:
        # Update reset time to prevent spam (alert once per 24h period)
        print("Data over threshold for 24+ hours")
        write_redemption_cache(current_usage, current_time)
        return True

    # No significant change - don't save cache, just continue monitoring
    print(
        f"Cached usage: {cached_usage}, Last reset time: {last_reset_time}, Current usage: {current_usage}, Threshold: {threshold}"
    )
    return False


def _reserves_cache_key(metric: str) -> str:
    return f"{PROTOCOL}_RESERVES_{metric}"


def _get_cached_float(cache_key: str) -> float | None:
    cached = get_last_value_for_key_from_file(cache_filename, cache_key)
    if cached == 0:
        return None
    try:
        return float(cached)
    except ValueError:
        return None


def _set_cached_float(cache_key: str, value: float) -> None:
    write_last_value_to_file(cache_filename, cache_key, f"{value}")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _normalize_text(text: str) -> str:
    text = _strip_html(text)
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\[\d+\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_value(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _parse_compact_usd(raw: str) -> float:
    value = raw.replace("$", "").replace(",", "").replace(" ", "").strip()
    sign = -1 if value.startswith("-") else 1
    value = value.lstrip("-").lstrip("+")
    if value.startswith("−"):
        sign = -1
        value = value.lstrip("−")
    multiplier = 1.0
    if value.endswith("K"):
        multiplier = 1_000.0
        value = value[:-1]
    elif value.endswith("M"):
        multiplier = 1_000_000.0
        value = value[:-1]
    elif value.endswith("B"):
        multiplier = 1_000_000_000.0
        value = value[:-1]
    return sign * float(value) * multiplier


def _parse_percent(raw: str) -> float:
    return float(raw.replace("%", "").replace(",", "").strip())


def _format_usd(value: float) -> str:
    return f"${value:,.2f}"


def _parse_reserves_timestamp(text: str) -> datetime | None:
    match = re.search(r"RESOLV PROOF OF RESERVES\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{2}:\d{2}\s+UTC)", text)
    if not match:
        return None
    raw = match.group(1)
    year = datetime.utcnow().year
    try:
        ts = datetime.strptime(f"{raw} {year}", "%d %b %H:%M UTC %Y")
    except ValueError:
        return None
    if ts > datetime.utcnow() + timedelta(days=1):
        ts = ts.replace(year=year - 1)
    return ts


def fetch_resolv_reserves_html() -> str | None:
    """Fetch Resolv reserves page HTML."""
    try:
        resp = requests.get(RESOLV_RESERVES_URL, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code} for {RESOLV_RESERVES_URL}")
            return None
        return resp.text
    except Exception as e:
        print(f"Failed to fetch {RESOLV_RESERVES_URL}: {e}")
        return None


def parse_resolv_reserves_metrics(html: str) -> tuple[dict[str, float], list[str], datetime | None]:
    text = _normalize_text(html)
    metrics: dict[str, float] = {}
    missing: list[str] = []

    def _add_metric(label: str, pattern: str, parser, key: str) -> None:
        raw = _extract_value(pattern, text)
        if raw is None:
            missing.append(label)
            return
        try:
            metrics[key] = parser(raw)
        except ValueError:
            missing.append(label)

    _add_metric("TVL", r"(?<!USR )(?<!RLP )TVL:\s*\$([0-9.,]+[KMB]?)", _parse_compact_usd, "tvl_usd")
    _add_metric("USR TVL", r"USR TVL:\s*\$([0-9.,]+[KMB]?)", _parse_compact_usd, "usr_tvl_usd")
    _add_metric("RLP TVL", r"RLP TVL:\s*\$([0-9.,]+[KMB]?)", _parse_compact_usd, "rlp_tvl_usd")
    _add_metric("RLP/USR ratio", r"RLP/USR ratio:\s*([\-0-9.,]+%)", _parse_percent, "rlp_usr_ratio_pct")
    _add_metric(
        "Backing assets value",
        r"Backing assets value:\s*\$([\-0-9.,]+[KMB]?)",
        _parse_compact_usd,
        "backing_assets_usd",
    )
    _add_metric(
        "Market delta",
        r"Market delta[^:]*:\s*([\-0-9.,]+%)",
        _parse_percent,
        "market_delta_pct",
    )
    _add_metric(
        "Strategy net exposure",
        r"Strategy net exposure[^:]*:\s*([\-+]?\s*\$?[0-9.,]+[KMB]?)",
        _parse_compact_usd,
        "strategy_net_exposure_usd",
    )

    timestamp = _parse_reserves_timestamp(text)
    return metrics, missing, timestamp


def _check_metric_change_ratio(
    metric_key: str,
    label: str,
    current: float,
    ratio_trigger: float,
    error_messages: list[str],
    cache: dict[str, float | None],
) -> None:
    """Check if metric changed by ratio threshold and alert if so."""
    cache_key = _reserves_cache_key(metric_key)
    cached = cache.get(cache_key)
    if cached is not None and cached > 0:
        change_ratio = abs(current - cached) / cached
        if change_ratio >= ratio_trigger:
            error_messages.append(
                f"⚠️ Resolv reserves {label} changed by {change_ratio * 100:.2f}% "
                f"({_format_usd(cached)} → {_format_usd(current)})"
            )
    cache[cache_key] = current


def _check_metric_change_abs(
    metric_key: str,
    label: str,
    current: float,
    abs_trigger: float,
    error_messages: list[str],
    cache: dict[str, float | None],
    unit: str = "%",
) -> None:
    cache_key = _reserves_cache_key(metric_key)
    cached = cache.get(cache_key)
    if cached is not None:
        delta = abs(current - cached)
        if delta >= abs_trigger:
            error_messages.append(
                f"⚠️ Resolv reserves {label} moved by {delta:.2f}{unit} ({cached:.2f}{unit} → {current:.2f}{unit})"
            )
    cache[cache_key] = current


def _load_all_cache_values(metric_keys: list[str]) -> dict[str, float | None]:
    """Load all cache values at once to avoid repeated file I/O."""
    cache: dict[str, float | None] = {}
    cache_keys = [_reserves_cache_key(key) for key in metric_keys]

    # Read cache file once
    if not os.path.exists(cache_filename):
        return {key: None for key in cache_keys}

    # Parse entire file once
    file_cache: dict[str, str] = {}
    with open(cache_filename, "r") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                file_cache[key] = value

    # Extract only the keys we need
    for cache_key in cache_keys:
        cached_value = file_cache.get(cache_key, "0")
        if cached_value == "0":
            cache[cache_key] = None
        else:
            try:
                cache[cache_key] = float(cached_value)
            except ValueError:
                cache[cache_key] = None

    return cache


def _save_all_cache_values(cache: dict[str, float | None]) -> None:
    """Save all cache values at once to avoid repeated file I/O."""
    if not cache:
        return

    # Read existing cache file
    file_cache: dict[str, str] = {}
    if os.path.exists(cache_filename):
        with open(cache_filename, "r") as f:
            for line in f:
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    file_cache[key] = value

    # Update with new values
    for cache_key, value in cache.items():
        if value is not None:
            file_cache[cache_key] = f"{value}"

    # Write entire file once
    with open(cache_filename, "w") as f:
        for key, value in file_cache.items():
            f.write(f"{key}:{value}\n")


def process_resolv_reserves_metrics(error_messages: list[str]) -> None:
    html = fetch_resolv_reserves_html()
    if html is None:
        error_messages.append("⚠️ Resolv reserves: failed to fetch off-chain data.")
        return

    metrics, missing, timestamp = parse_resolv_reserves_metrics(html)
    if missing:
        error_messages.append(f"⚠️ Resolv reserves: missing fields: {', '.join(missing)}")
    if not metrics:
        error_messages.append("⚠️ Resolv reserves: failed to parse any metrics.")
        return

    if timestamp is None:
        error_messages.append("⚠️ Resolv reserves: timestamp missing or unparseable.")
    else:
        max_age = timedelta(hours=RESERVES_DATA_MAX_AGE_HOURS)
        if datetime.utcnow() - timestamp > max_age:
            error_messages.append(f"⚠️ Resolv reserves data is stale: {timestamp} UTC")

    if "usr_over_collateralization_pct" in metrics:
        if metrics["usr_over_collateralization_pct"] < USR_OVER_COLLATERALIZATION_MIN_PCT:
            error_messages.append(
                f"⚠️ Resolv USR over-collateralization below threshold: {metrics['usr_over_collateralization_pct']:.2f}%"
            )

    if "market_delta_pct" in metrics and abs(metrics["market_delta_pct"]) > MARKET_DELTA_ABS_PCT_TRIGGER:
        error_messages.append(
            "⚠️ Resolv market delta out of range: "
            f"{metrics['market_delta_pct']:.2f}% (threshold {MARKET_DELTA_ABS_PCT_TRIGGER:.2f}%)"
        )

    if "strategy_net_exposure_usd" in metrics and "tvl_usd" in metrics and metrics["tvl_usd"] > 0:
        net_ratio = abs(metrics["strategy_net_exposure_usd"]) / metrics["tvl_usd"]
        if net_ratio > NET_EXPOSURE_TVL_RATIO_TRIGGER:
            error_messages.append(
                "⚠️ Resolv strategy net exposure too large: "
                f"{_format_usd(metrics['strategy_net_exposure_usd'])} "
                f"({net_ratio * 100:.2f}% of TVL)"
            )

    # Load all cache values once
    metric_keys_to_check = ["tvl_usd", "usr_tvl_usd", "rlp_tvl_usd", "backing_assets_usd", "rlp_usr_ratio_pct"]
    cache = _load_all_cache_values(metric_keys_to_check)

    # Check percentage-based change metrics
    ratio_metrics = [
        ("tvl_usd", "TVL", TVL_CHANGE_RATIO_TRIGGER),
        ("usr_tvl_usd", "USR TVL", USR_TVL_CHANGE_RATIO_TRIGGER),
        ("rlp_tvl_usd", "RLP TVL", RLP_TVL_CHANGE_RATIO_TRIGGER),
        ("backing_assets_usd", "backing assets value", BACKING_ASSETS_CHANGE_RATIO_TRIGGER),
    ]
    for metric_key, label, trigger in ratio_metrics:
        if metric_key in metrics:
            _check_metric_change_ratio(metric_key, label, metrics[metric_key], trigger, error_messages, cache)

    # Check absolute change metric (percentage points)
    if "rlp_usr_ratio_pct" in metrics:
        _check_metric_change_abs(
            "rlp_usr_ratio_pct",
            "RLP/USR ratio",
            metrics["rlp_usr_ratio_pct"],
            RLP_USR_RATIO_PCT_CHANGE_TRIGGER,
            error_messages,
            cache,
        )

    # Save all cache values once
    _save_all_cache_values(cache)


def main() -> None:
    client = ChainManager.get_client(Chain.MAINNET)

    try:
        usr_price_storage = client.eth.contract(address=USR_PRICE_STORAGE, abi=ABI_USR_PRICE_STORAGE)
        usr_redemption = client.eth.contract(address=USR_REDEMPTION, abi=ABI_USR_REDEMPTION)
    except Exception as e:
        error_message = f"Error creating contract instances: {e}. Check ABI paths and contract addresses."
        print(error_message)
        return  # Cannot proceed without contracts

    # Combined blockchain calls
    try:
        with client.batch_requests() as batch:
            batch.add(usr_redemption.functions.redemptionLimit())
            batch.add(usr_redemption.functions.currentRedemptionUsage())
            batch.add(usr_price_storage.functions.lastPrice())

            responses = client.execute_batch(batch)

            if len(responses) != 3:
                error_message = f"Batch Call: Expected 3 responses, got {len(responses)}"
                print(error_message)
                send_telegram_message(error_message, PROTOCOL, True, True)
                return

            redemption_limit, current_redemption_usage, usr_last_price = responses
            print(
                f"Raw Data - Redemption Limit: {redemption_limit}, "
                f"Current Redemption Usage: {current_redemption_usage}, "
                f"USR Last Price: {usr_last_price}"
            )
            usr_price, usr_supply, reserves, timestamp = usr_last_price

    except Exception as e:
        error_message = f"Error during batch blockchain calls: {e}"
        send_telegram_message(error_message, PROTOCOL, True, True)
        return

    error_messages = []

    if usr_price != WEI_PER_ETHER:
        error_messages.append(
            f"USR Price is not {WEI_PER_ETHER}!\n"
            f"USR Price: {usr_price / WEI_PER_ETHER:.4f}\n"
            f"USR Supply: {usr_supply / WEI_PER_ETHER:.4f}\n"
            f"Reserves: {reserves / WEI_PER_ETHER:.4f}\n"
            f"Timestamp: {timestamp}"
        )

    if usr_supply > 0:
        over_collateralization_pct = (reserves / usr_supply) * 100
        if over_collateralization_pct < USR_OVER_COLLATERALIZATION_MIN_PCT:
            error_messages.append(
                "USR over-collateralization below threshold!\n"
                f"Over-collateralization: {over_collateralization_pct:.2f}%\n"
                f"USR Supply: {usr_supply / WEI_PER_ETHER:.4f}\n"
                f"Reserves: {reserves / WEI_PER_ETHER:.4f}"
            )
    else:
        error_messages.append(
            "USR supply is zero or invalid, cannot compute over-collateralization.\n"
            f"USR Supply: {usr_supply}\n"
            f"Reserves: {reserves}"
        )

    if should_alert_redemption(current_redemption_usage, redemption_limit):
        error_messages.append(
            "Current Redemption Usage is greater than 50% of Redemption Limit!\n"
            f"Current Redemption Usage: {current_redemption_usage / WEI_PER_ETHER:.4f}\n"
            f"Redemption Limit: {redemption_limit / WEI_PER_ETHER:.4f}\n"
            f"Available redemption: {(redemption_limit - current_redemption_usage) / WEI_PER_ETHER:.4f}"
        )

    # Check if timestamp is older than one day
    current_time = int(time.time())
    if timestamp < current_time - ONE_DAY_SECONDS:
        error_messages.append(
            f"⚠️ USR data is stale!\n"
            f"Last update: {datetime.fromtimestamp(timestamp)}\n"
            f"Current time: {datetime.fromtimestamp(current_time)}"
        )

    process_resolv_reserves_metrics(error_messages)

    if error_messages:
        send_telegram_message("\n".join(error_messages), PROTOCOL)


if __name__ == "__main__":
    main()
