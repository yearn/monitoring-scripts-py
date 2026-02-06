from datetime import datetime, timedelta

import requests

from utils.logging import get_logger
from utils.telegram import send_telegram_message

PROTOCOL = "moonwell"
logger = get_logger(PROTOCOL)

BAD_DEBT_RATIO = 0.005  # 0.5%
DEBT_SUPPLY_RATIO = 0.70  # 70%

BASE_URL = "https://services.defirisk.sentora.com/metric/base/moonwell"


def get_timestamp_before(hours: int):
    """Get timestamp from hours ago in ISO format"""
    now = datetime.utcnow()
    hours_ago = now - timedelta(hours=hours)
    return hours_ago.strftime("%Y-%m-%dT%H:00:00.000Z")


def fetch_metrics():
    """Fetch all required metrics from Sentora API about Moonwell"""
    metrics = {}
    error_messages = []
    endpoints = {
        "total_supply": "general/total_supply",
        "total_debt": "general/total_debt",
        "bad_debt": "liquidation/health_factor_distribution",
    }

    # Get timestamp from 48 hours ago because over the weekend the data is not updated.
    timestamp = get_timestamp_before(hours=48)

    for metric_name, endpoint in endpoints.items():
        url = f"{BASE_URL}/{endpoint}?since={timestamp}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("metric") or len(data["metric"]) == 0:
                error_messages.append(f"No data returned for {metric_name}")
                metrics[metric_name] = 0
                continue

            metrics[metric_name] = data["metric"][-1][1]  # Get latest value

        except Exception as e:
            error_messages.append(f"Error fetching {metric_name}: {str(e)}")
            metrics[metric_name] = 0

    # Send combined error messages if any
    if error_messages:
        combined_message = "Errors occurred:" + "\n".join(error_messages)
        logger.error("%s", combined_message)
        return {}
    return metrics


def check_thresholds(metrics):
    """Check if any metrics exceed thresholds and send alerts"""
    total_supply = metrics["total_supply"]
    total_debt = metrics["total_debt"]
    bad_debt = metrics["bad_debt"]

    # If there is no supply or debt, skip the checks
    if total_supply == 0 or total_debt == 0:
        send_telegram_message("🚨 Moonwell metrics are all 0", PROTOCOL, disable_notification=True)
        return

    tvl = total_supply - total_debt

    # Calculate ratios
    bad_debt_ratio = bad_debt / tvl if tvl > 0 else 0
    debt_supply_ratio = total_debt / total_supply if total_supply > 0 else 0
    logger.info("Total supply: %s", f"{total_supply:,.2f}")
    logger.info("Total debt: %s", f"{total_debt:,.2f}")
    logger.info("TVL: %s", f"{tvl:,.2f}")
    logger.info("Bad debt: %s", f"{bad_debt:,.2f}")
    logger.info("Bad debt ratio: %s", f"{bad_debt_ratio:.2%}")
    logger.info("Debt supply ratio: %s", f"{debt_supply_ratio:.2%}")

    alerts = []

    # Check bad debt ratio
    if bad_debt_ratio > BAD_DEBT_RATIO:
        alerts.append(
            f"🚨 High Bad Debt Alert:\n"
            f"💀 Bad Debt Ratio: {bad_debt_ratio:.2%}\n"
            f"💰 Bad Debt: ${bad_debt:,.2f}\n"
            f"📊 TVL: ${tvl:,.2f}"
        )

    # Check debt/supply ratio
    if debt_supply_ratio > DEBT_SUPPLY_RATIO:
        alerts.append(
            f"⚠️ High Debt/Supply Ratio Alert:\n"
            f"📈 Debt/Supply Ratio: {debt_supply_ratio:.2%}\n"
            f"💸 Total Debt: ${total_debt:,.2f}\n"
            f"💰 Total Supply: ${total_supply:,.2f}"
        )

    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)


def main():
    metrics = fetch_metrics()
    if len(metrics) == 3:
        check_thresholds(metrics)
    else:
        send_telegram_message(
            "🚨 Moonwell metrics cannot be fetched from any source",
            PROTOCOL,
            disable_notification=True,
        )


if __name__ == "__main__":
    main()
