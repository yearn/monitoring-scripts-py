# Yearn Monitoring

This folder contains monitoring scripts for Yearn vault activity and timelock operations.

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

=======

## Endorsed Vault Check

The script `yearn/check_endorsed.py` verifies that all Yearn v3 vaults listed in the yDaemon API are actually endorsed on-chain in the registry contract. It runs [weekly via GitHub Actions](../.github/workflows/weekly.yml).

### How It Works

For each supported chain (Mainnet, Polygon, Base, Arbitrum, Katana):

1. Fetches all v3 vault addresses from the [yDaemon API](https://ydaemon.yearn.fi).
2. Calls `isEndorsed(address)` on the registry contract (`0xd40ecF29e001c76Dcc4cC0D9cd50520CE845B038`).
3. Collects any vault that is listed in yDaemon but **not** endorsed on-chain.

### Alerts

If any unendorsed vaults are found, a Telegram alert is sent to the Yearn group listing each address grouped by chain. If the message exceeds the Telegram character limit, a short summary with a link to the GitHub Actions logs is sent instead.

### Usage

```bash
uv run yearn/check_endorsed.py
```

=======

## Timelock Monitoring

Yearn TimelockController contracts are monitored across 6 chains via the shared [timelock monitoring script](../timelock/README.md). Alerts are routed to the `YEARN` Telegram channel.

### Monitored Addresses

All chains use the same contract address: `0x88ba032be87d5ef1fbe87336b7090767f367bf73`

| Chain | Explorer |
|-------|----------|
| Mainnet | [etherscan.io](https://etherscan.io/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |
| Base | [basescan.org](https://basescan.org/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |
| Arbitrum | [arbiscan.io](https://arbiscan.io/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |
| Polygon | [polygonscan.com](https://polygonscan.com/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |
| Katana | [katanascan.com](https://katanascan.com/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |
| Optimism | [optimistic.etherscan.io](https://optimistic.etherscan.io/address/0x88ba032be87d5ef1fbe87336b7090767f367bf73) |

