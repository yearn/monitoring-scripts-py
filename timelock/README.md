# Timelock Monitoring

Monitors all timelock contract types (TimelockController, Aave, Compound, Puffer, Lido) and sends Telegram alerts to protocol-specific channels.

## How It Works

1. Queries the Envio GraphQL indexer (`ENVIO_GRAPHQL_URL`) for new `TimelockEvent` events across all monitored timelocks (all types).
2. Groups events by `operationId` so batch operations (`scheduleBatch`) are sent as a single alert.
3. Routes each alert to the correct Telegram channel based on the protocol mapping.
4. Stores the latest processed `blockTimestamp` in `cache-id.txt` (key: `TIMELOCK_LAST_TS`) to avoid duplicate alerts between runs.

The script runs [hourly via GitHub Actions](../.github/workflows/hourly.yml).

## GraphQL Schema

The script queries the unified `TimelockEvent` type from the Envio indexer. The query fetches all timelock types (TimelockController, Aave, Compound, Puffer, Lido) for monitored addresses.

### Query Structure

```graphql
query GetTimelockEvents($limit: Int!, $sinceTs: Int!, $addresses: [String!]!) {
  TimelockEvent(
    where: {
      timelockAddress: { _in: $addresses }
      blockTimestamp: { _gt: $sinceTs }
    }
    order_by: { blockTimestamp: asc, blockNumber: asc, logIndex: asc }
    limit: $limit
  ) {
    id
    timelockAddress
    timelockType
    eventName
    chainId
    blockNumber
    blockTimestamp
    transactionHash
    operationId
    index
    target
    value
    data
    predecessor
    delay
    signature
    creator
    metadata
    votesFor
    votesAgainst
  }
}
```

### Schema Fields

The `TimelockEvent` type includes fields that vary by timelock type:

**Common fields (all types):**
- **`id`** - Unique identifier: `${chainId}_${blockNumber}_${logIndex}`
- **`timelockAddress`** - Address of the timelock contract
- **`timelockType`** - Type discriminator: `"TimelockController"`, `"Aave"`, `"Compound"`, `"Puffer"`, or `"Lido"`
- **`eventName`** - Original event name (e.g., `"CallScheduled"`, `"ProposalQueued"`, `"QueueTransaction"`, etc.)
- **`chainId`** - Chain ID (1 for Mainnet, 8453 for Base, etc.)
- **`blockNumber`** - Block number where the event was emitted
- **`blockTimestamp`** - Unix timestamp of the block
- **`transactionHash`** - Transaction hash
- **`operationId`** - Unified identifier for the queued operation

**Type-specific fields:**
- **TimelockController**: `target`, `value`, `data`, `delay` (relative seconds), `predecessor`, `index`
- **Aave**: `votesFor`, `votesAgainst`, `operationId` (proposalId)
- **Compound**: `target`, `value`, `data`, `delay` (absolute timestamp/eta), `signature`, `operationId` (txHash)
- **Puffer**: `target`, `data`, `delay` (absolute timestamp/lockedUntil), `operationId` (txHash)
- **Lido**: `creator`, `metadata`, `operationId` (voteId)

For complete field mapping details, see [`detils.md`](./detils.md).

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
| [0x2eFF...26b](https://etherscan.io/address/0x2efff88747eb5a3ff00d4d8d0f0800e306c0426b) | Mainnet | MAPLE | Maple GovernorTimelock |
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

The alert format varies by timelock type:

**TimelockController/Compound/Puffer:**
```
⏰ TIMELOCK: New Operation Scheduled
🅿️ Protocol: LRT
📋 Timelock: EtherFi Timelock
🔗 Chain: Mainnet
📌 Type: TimelockController
📝 Event: CallScheduled
⏳ Delay: 2d
🎯 Target: 0x1234...
📝 Function: 0xabcdef12
🔗 Tx: https://etherscan.io/tx/0x...
```

**Aave:**
```
⏰ TIMELOCK: New Operation Scheduled
🅿️ Protocol: AAVE
📋 Timelock: Aave Timelock
🔗 Chain: Mainnet
📌 Type: Aave
📝 Event: ProposalQueued
✅ Votes For: 12345
❌ Votes Against: 6789
🆔 Proposal ID: 42
🔗 Tx: https://etherscan.io/tx/0x...
```

**Lido:**
```
⏰ TIMELOCK: New Operation Scheduled
🅿️ Protocol: LIDO
📋 Timelock: Lido DAO
🔗 Chain: Mainnet
📌 Type: Lido
📝 Event: StartVote
👤 Creator: 0x1234...
📄 Metadata: ipfs://...
🆔 Vote ID: 123
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

The script stores the latest processed `blockTimestamp` in `cache-id.txt` under key `TIMELOCK_LAST_TS`. This value is universal across chains (unlike block numbers) so a single cache entry covers all monitored timelocks. On the first run (or with `--no-cache`), it falls back to querying events from the last 2 hours.

## Schema Details

For comprehensive information about the unified `TimelockEvent` schema, including field mappings for all supported timelock types (TimelockController, Aave, Compound, Puffer, Lido), see [`detils.md`](./detils.md).
