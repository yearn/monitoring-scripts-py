
# Euler

## Governance

Github actions bot that check every hour if there are queued transactions in [Safe Multisig (4/7)](https://app.safe.global/transactions/queue?safe=eth%3A0xcAD001c30E96765aC90307669d578219D4fb1DCe). Sends telegram message for new queued transactions.

## Data Monitoring

The script [bad_debt.py](bad_debt.py) is run hourly by Github actions. It fetches the data from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler) and sends alerts if the thresholds are exceeded. If both data sources are not working, it sends an alert.

### Value at Risk

The alerts are sent when the [value at risk](bad_debt.py#L52) is greater than 1% of the total debt. The data is fetched from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler).

### Liquidation at Risk

The alerts are sent when the [liquidation at risk](bad_debt.py#L65) is greater than 5% of the total debt. The data is fetched from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler).

### Debt Supply Ratio

The script fetches the data from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler) and sends alerts if the debt supply ratio is greater than 70%.
