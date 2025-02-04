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


def fetch_metric_from_gauntlet():
    # TODO: verify if the key after data needs to be changed
    urlHealthMetrics = "https://dashboards.gauntlet.xyz/_next/data/qA1T3oa5dRRXh5ya1_q5Y/protocols/moonwell.json?protocolSlug=moonwell"
    alerts = []
    response = requests.get(urlHealthMetrics)
    response.raise_for_status()
    data = response.json()
    markets = data["pageProps"]["protocolPage"]["markets"]
    for market in markets:
        if market["key"] == "base":
            market_data = market["data"]
            last_updated = market_data["borrow"]["lastUpdated"]
            if last_updated < get_timestamp_before(hours=6):
                # don't accept data older than 6 hours
                alerts.append(
                    f"🚨 Market is not updated for {market['key']} - last updated {last_updated}"
                )
                break

            borrow_amount = market_data["borrow"]["amount"]
            supply_amount = market_data["supply"]["amount"]
            debt_supply_ratio = (
                borrow_amount / supply_amount if supply_amount > 0 else 0
            )
            if debt_supply_ratio > DEBT_SUPPLY_RATIO:
                alerts.append(
                    f"🚨 High Debt/Supply Ratio Alert:\n"
                    f"📈 Debt/Supply Ratio: {debt_supply_ratio:.2%}\n"
                    f"💸 Total Debt: ${borrow_amount:.2f}\n"
                    f"💰 Total Supply: ${supply_amount:.2f}"
                )

            # VaR conveys capital at risk due to insolvencies when markets are under duress (i.e., Black Thursday)
            value_at_risk = market_data["var"]["amount"]
            if value_at_risk / borrow_amount > 0.01:
                # for more info check: https://www.gauntlet.xyz/resources/improved-var-methodology
                alerts.append(
                    f"🚨 Value at Risk Alert:\n"
                    f"💸 Value at Risk: ${value_at_risk:.2f}\n"
                    f"💸 Total Debt: ${borrow_amount:.2f}\n"
                    f"💰 Total Supply: ${supply_amount:.2f}"
                )

            # LaR conveys capital at risk due to liquidations when markets are under duress.
            liquidation_at_risk = market_data["lar"]["amount"]
            if liquidation_at_risk / borrow_amount > 0.05:
                # for more info check: https://www.gauntlet.xyz/resources/improved-lar-methodology
                alerts.append(
                    f"🚨 Liquidation at Risk Alert:\n"
                    f"💸 Liquidation at Risk: ${liquidation_at_risk:.2f}\n"
                    f"💸 Total Debt: ${borrow_amount:.2f}\n"
                    f"💰 Total Supply: ${supply_amount:.2f}"
                )
        return True

    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)
    return False


def fetch_metrics():
    """Fetch all required metrics from IntoTheBlock API about Moonwell"""
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
        # send_telegram_message(combined_message, PROTOCOL)
        print(combined_message)
        return {}
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
    if len(metrics) == 3:
        check_thresholds(metrics)
    successfull = fetch_metric_from_gauntlet()
    if not successfull and len(metrics) != 3:
        # if both data sources are not working, send an alert
        send_telegram_message("🚨 Moonwell metrics cannot be fetched", PROTOCOL)


if __name__ == "__main__":
    main()
