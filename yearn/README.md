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

### Alert Format

```
⏰ TIMELOCK: New Operation Scheduled
🅿️ Protocol: YEARN
📋 Timelock: Yearn TimelockController
🔗 Chain: Mainnet
📌 Type: TimelockController
📝 Event: CallScheduled
⏳ Delay: 2d
🎯 Target: 0x1234...
📝 Function: 0xabcdef12
🔗 Tx: https://etherscan.io/tx/0x...
```

For batch operations (`scheduleBatch`), all calls are included in a single message with `--- Call N ---` separators.
