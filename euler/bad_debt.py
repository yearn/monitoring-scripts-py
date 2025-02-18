from utils.telegram import send_telegram_message
from utils.gauntlet import get_markets_for_protocol, format_usd, get_timestamp_before

PROTOCOL = "EULER"
DEBT_SUPPLY_RATIO = 0.70  # 70%
# available markets: https://dashboards.gauntlet.xyz/protocols/euler
USED_EULER_VAULTS_KEYS = ["ethereum-prime", "ethereum-yield"]


def fetch_metric_from_gauntlet(max_retries=3):
    alerts = []
    markets = get_markets_for_protocol(PROTOCOL, max_retries)
    print(markets)

    if not markets:
        return False

    for market in markets:
        if market["key"] in USED_EULER_VAULTS_KEYS:
            market_data = market["data"]
            last_updated = market_data["borrow"]["lastUpdated"]
            if last_updated < get_timestamp_before(hours=6):
                alerts.append(
                    f"🚨 Market is not updated for {market['label']} - last updated {last_updated}"
                )
                break

            borrow_amount = market_data["borrow"]["amount"]
            supply_amount = market_data["supply"]["amount"]
            debt_supply_ratio = (
                borrow_amount / supply_amount if supply_amount > 0 else 0
            )
            if debt_supply_ratio > DEBT_SUPPLY_RATIO:
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"📈 Debt/Supply Ratio: {debt_supply_ratio:.2%}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

            # VaR conveys capital at risk due to insolvencies when markets are under duress (i.e., Black Thursday)
            value_at_risk = market_data["var"]["amount"]
            if value_at_risk / borrow_amount > 0.01:  # 1%
                # for more info check: https://www.gauntlet.xyz/resources/improved-var-methodology
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"💸 Value at Risk: {format_usd(value_at_risk)}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

            # LaR conveys capital at risk due to liquidations when markets are under duress.
            liquidation_at_risk = market_data["lar"]["amount"]
            if liquidation_at_risk / borrow_amount > 0.05:  # 5%
                # for more info check: https://www.gauntlet.xyz/resources/improved-var-methodology
                alerts.append(
                    f"🚨 Euler Market: {market['label']} is at risk:\n"
                    f"💸 Liquidation at Risk: {format_usd(liquidation_at_risk)}\n"
                    f"💸 Total Debt: {format_usd(borrow_amount)}\n"
                    f"💰 Total Supply: {format_usd(supply_amount)}\n"
                    f"🕒 Last Updated: {last_updated}"
                )

    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)

    return True


def main():
    successfull = fetch_metric_from_gauntlet()
    if not successfull:
        # if both data sources are not working, send an alert
        send_telegram_message("🚨 Euler metrics cannot be fetched", PROTOCOL)

    # TODO: implement checks for vault allocations

if __name__ == "__main__":
    main()
