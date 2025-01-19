import requests
from datetime import datetime, timedelta
from utils.telegram import send_telegram_message

PROTOCOL = "MOONWELL"
BASE_URL = "https://services.defirisk.intotheblock.com/metric/base/moonwell"
BAD_DEBT_RATIO = 0.005  # 0.5%
DEBT_SUPPLY_RATIO = 0.70  # 70%


def get_timestamp_before(hours: int):
    """Get timestamp from one hour ago in ISO format"""
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=hours)
    return one_hour_ago.strftime("%Y-%m-%dT%H:00:00.000Z")


def fetch_metrics():
    """Fetch all required metrics from IntoTheBlock API about Moonwell"""
    metrics = {}
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
                message = f"No data returned for {metric_name}"
                send_telegram_message(message, PROTOCOL)
                metrics[metric_name] = 0
                continue

            metrics[metric_name] = data["metric"][-1][1]  # Get latest value

        except Exception as e:
            message = f"Error fetching {metric_name}: {str(e)}"
            send_telegram_message(message, PROTOCOL)
            metrics[metric_name] = 0

    return metrics


def check_thresholds(metrics):
    """Check if any metrics exceed thresholds and send alerts"""
    total_supply = metrics["total_supply"]
    total_debt = metrics["total_debt"]
    bad_debt = metrics["bad_debt"]

    # If there is no supply or debt, skip the checks
    if total_supply == 0 or total_debt == 0:
        return

    tvl = total_supply - total_debt

    # Calculate ratios
    bad_debt_ratio = bad_debt / tvl if tvl > 0 else 0
    debt_supply_ratio = total_debt / total_supply if total_supply > 0 else 0

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
    check_thresholds(metrics)


if __name__ == "__main__":
    main()
