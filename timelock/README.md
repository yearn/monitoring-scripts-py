# Timelock Monitoring

Monitors [OpenZeppelin TimelockController](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/governance/TimelockController.sol) contracts for `CallScheduled` events and sends Telegram alerts to protocol-specific channels.

## How It Works

1. Queries the Envio GraphQL indexer (`ENVIO_GRAPHQL_URL`) for new `CallScheduled` events across all monitored timelocks.
2. Groups events by `operationId` so batch operations (`scheduleBatch`) are sent as a single alert.
3. Routes each alert to the correct Telegram channel based on the protocol mapping.
4. Stores the latest processed `blockTimestamp` in `cache-id.txt` (key: `TIMELOCK_LAST_TS`) to avoid duplicate alerts between runs.

The script runs [hourly via GitHub Actions](../.github/workflows/hourly.yml).

## Monitored Timelocks

| Address | Chain | Protocol | Label |
|---------|-------|----------|-------|
| [0xd823...9ab](https://etherscan.io/address/0xd8236031d8279d82e615af2bfab5fc0127a329ab) | Mainnet | CAP | CAP TimelockController |
| [0x5d8a...556](https://etherscan.io/address/0x5d8a7dc9405f08f14541ba918c1bf7eb2dace556) | Mainnet | RTOKEN | ETH+ Timelock |
| [0x055e...e59](https://etherscan.io/address/0x055e84e7fe8955e2781010b866f10ef6e1e77e59) | Mainnet | LRT | Lombard TimeLock |
| [0xe1f0...d22](https://etherscan.io/address/0xe1f03b7b0ebf84e9b9f62a1db40f1efb8faa7d22) | Mainnet | SILO | Silo TimelockController |
| [0x81f6...cc7](https://etherscan.io/address/0x81f6e9914136da1a1d3b1efd14f7e0761c3d4cc7) | Mainnet | LRT | Renzo(ezETH) TimelockController |
| [0x9f26...761](https://etherscan.io/address/0x9f26d4c958fd811a1f59b01b86be7dffc9d20761) | Mainnet | LRT | EtherFi Timelock |
| [0x49bd...3b1](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1) | Mainnet | LRT | KelpDAO(rsETH) Timelock |
| [0xf817...4f](https://basescan.org/address/0xf817cb3092179083c48c014688d98b72fb61464f) | Base | LRT | superOETH Timelock |

## How to Add a New Timelock

1. **Add the address to the Envio indexer config.** The address must be indexed before this script can query events for it. Open the [Envio config.yaml](https://github.com/chain-events/yearn-indexing-test/blob/main/config.yaml), add the address under the correct chain's `TimelockController` contract list, and deploy the updated indexer.

2. **Add a `TimelockConfig` entry** in [`timelock_alerts.py`](./timelock_alerts.py) in the `TIMELOCK_LIST` list:

```python
TimelockConfig("0xabcdef...lowercase_address", 1, "PROTOCOL_NAME", "Human Readable Label"),
```

Parameters:
- **address**: Timelock contract address, **must be lowercase**.
- **chain_id**: Chain ID (`1` for Mainnet, `8453` for Base, etc.). Must match the network in the Envio config.
- **protocol**: Protocol identifier used for Telegram routing. Maps to `TELEGRAM_CHAT_ID_{PROTOCOL}` and `TELEGRAM_BOT_TOKEN_{PROTOCOL}` env variables. Falls back to `TELEGRAM_BOT_TOKEN_DEFAULT` if no protocol-specific bot token exists.
- **label**: Human-readable name shown in the alert message.

3. If the chain is new, make sure it exists in [`utils/chains.py`](../utils/chains.py) (`Chain` enum and `EXPLORER_URLS` dict).
4. If the protocol needs a dedicated Telegram channel, add `TELEGRAM_CHAT_ID_{PROTOCOL}` and optionally `TELEGRAM_BOT_TOKEN_{PROTOCOL}` to the environment and GitHub Actions secrets.

## Alert Format

```
⏰ TIMELOCK: New Operation Scheduled
🅿️ Protocol: LRT
📋 Timelock: EtherFi Timelock
🔗 Chain: Mainnet
⏳ Delay: 2d
🎯 Target: 0x1234...
📝 Function: 0xabcdef12
🔗 Tx: https://etherscan.io/tx/0x...
```

For batch operations (`scheduleBatch`), all calls are included in a single message with `--- Call N ---` separators.

## Usage

```bash
uv run timelock/timelock_alerts.py
```

Optional flags:

- `--limit` — max events to fetch per run (default: `100`)
- `--since-seconds` — fallback lookback window when no cache exists (default: `7200` / 2h)
- `--no-cache` — disable caching, always use `--since-seconds` lookback
- `--log-level` — set log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `WARNING`)

## Caching

The script stores the latest processed `blockTimestamp` in `cache-id.txt` under key `TIMELOCK_LAST_BLOCK_TS`. This value is universal across chains (unlike block numbers) so a single cache entry covers all monitored timelocks. On the first run (or with `--no-cache`), it falls back to querying events from the last 2 hours.
