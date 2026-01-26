# Yearn Monitoring

This folder contains monitoring scripts for Yearn vault activity.

## Large Flows

The script `yearn/alert_large_flows.py` checks recent deposit and withdrawal events and sends a Telegram alert when a single flow exceeds a USD threshold. It runs [hourly via GitHub Actions](../.github/workflows/hourly.yml).

### Data Sources

- **Events**: Envio indexer GraphQL API (configurable via `ENVIO_GRAPHQL_URL`).
- **Pricing**: CoinGecko token prices for non-stables (uses `COINGECKO_API_KEY` if provided).
- **Fallback**: On-chain `totalSupply()` via ERC20 ABI when pricing fails.

### Alerts

An alert is emitted when a single deposit or withdrawal for a tracked vault is greater than the configured USD threshold (default: `5,000,000`). For stables, USD value is assumed to be the raw amount. For non-stables, if pricing fails, an alert triggers when the flow is >= 10% of the vault totalSupply. Alerts are sent in chronological order by block number and include vault and tx links.

### Caching

The script stores the last alerted transaction hash in `cache-id.txt` (key: `YEARN_LARGE_FLOW_LAST_TX`) to avoid duplicate alerts between hourly runs.

### Usage

```bash
uv run yearn/alert_large_flows.py
```

Optional flags:

- `--threshold-usd` (default: `5000000`)
- `--limit` (default: `100`)
- `--since-seconds` (default: `7200`)
- `--chain-ids` (default: `1`)
- `--no-cache` (disable caching)
