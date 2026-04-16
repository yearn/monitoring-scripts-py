# AI Transaction Explainer

Generates human-readable explanations for queued governance transactions (timelocks and Safe multisigs) by combining calldata decoding, Tenderly simulation, and LLM inference.

## Architecture

```
                     ┌─────────────────────┐
                     │  Governance Alert    │
                     │  (timelock / safe)   │
                     └──────────┬──────────┘
                                │ calldata (hex)
                                ▼
                     ┌─────────────────────┐
                     │  Calldata Decoder    │
                     │  (4byte + eth_abi)   │
                     └──────────┬──────────┘
                                │ DecodedCall(s)
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           ▼           ▼
          ┌──────────────┐ ┌──────────┐ ┌────────────────┐
          │   Tenderly   │ │  Proxy   │ │  LLM Provider  │
          │  Simulation  │ │ Detect   │ │  (factory)     │
          └──────┬───────┘ └────┬─────┘ └───────┬────────┘
                 │              │                │
                 └──────────────┼────────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  _build_prompt()     │
                     │  → LLM.complete()    │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Telegram Alert      │
                     │  🤖 AI Summary: ... │
                     └─────────────────────┘
```

## Pipeline Steps

### 1. Calldata Decoding (`timelock/calldata_decoder.py`)

Converts raw hex calldata into a structured `DecodedCall`:

1. Extract the 4-byte function selector (first 4 bytes after `0x`)
2. Look up the selector in `timelock/known_selectors.py` (local table)
3. If not found, query the [Sourcify 4byte API](https://api.4byte.sourcify.dev)
4. Parse the function signature to extract parameter types
5. Decode parameters using `eth_abi.decode()`

Result: `DecodedCall(function_name="upgradeTo", signature="upgradeTo(address)", params=[("address", "0x...")])`

### 2. Tenderly Simulation (`utils/tenderly/simulation.py`)

Simulates the transaction against current on-chain state to get:

- **Success/failure** status and gas used
- **Token transfers** (ERC-20 balance changes)
- **State changes** (storage slot diffs)
- **Emitted events** (decoded log entries)

Requires `TENDERLY_API_KEY` env var. Simulation failure is non-blocking -- the pipeline continues with decoded calldata only.

### 3. Proxy Upgrade Detection (`utils/proxy.py`)

If the calldata matches `upgradeTo(address)` or `upgradeToAndCall(address,bytes)`:

1. Extract the **new implementation** address from decoded params
2. Read the **current implementation** from the EIP-1967 storage slot (`0x360894a...`)
3. Build an Etherscan diff URL: `etherscan.io/contractdiffchecker?a1=old&a2=new`

This context is added to the LLM prompt so it can explain what changed in the upgrade.

### 4. LLM Prompt & Completion (`utils/llm/ai_explainer.py`)

The prompt is built from all available context:

```
System: You are a DeFi risk analyst explaining governance transactions...

Protocol: AAVE
Contract: Aave Governance V3
Target: 0x...

--- Decoded Calldata ---
Call 1: upgradeTo(address)
  address: 0xNewImpl

--- Proxy Upgrade ---
Current implementation: 0xOldImpl
New implementation: 0xNewImpl
Diff: https://etherscan.io/contractdiffchecker?a1=...&a2=...

--- Simulation Results ---
Simulation: SUCCESS
Gas used: 50,000
State changes (2 total, showing 2):
  ...
```

The full prompt is logged at INFO level for debugging. When running in GitHub Actions, the Telegram alert includes a "Full details" link to the CI logs.

### 5. Dual-Output Parsing

The LLM is asked to return two sections in a single response:

```
TLDR: Upgrades the AAVE pool implementation to 0xNew...

DETAIL:
This transaction calls upgradeTo(address) on the AAVE pool proxy...
Current implementation: 0xOld...
New implementation: 0xNew...
Risk: MEDIUM — verify new implementation is audited.
```

`_parse_explanation()` splits this into an `Explanation` dataclass:
- `summary` (from TLDR) — short, goes to Telegram
- `detail` (from DETAIL) — thorough analysis, logged at INFO level (visible in GH Actions)

If the LLM doesn't follow the format, the full response is used as the summary (backward compatible).

### 6. Output Formatting

`format_explanation_line()` uses only the summary for the Telegram message:

```
🤖 *AI Summary:*
Upgrades the AAVE pool implementation to 0xNew...
[Full details](https://github.com/.../actions/runs/123)
```

The "Full details" link points to GitHub Actions logs where the detailed analysis, full prompt, and simulation data are all logged.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `venice` | Provider name: `venice`, `groq`, `openai`, `anthropic`, or custom |
| `LLM_API_KEY` | *(required)* | API key for the LLM provider |
| `LLM_MODEL` | `grok-41-fast` | Model identifier |
| `LLM_BASE_URL` | *(per provider)* | API base URL (not needed for anthropic) |
| `TENDERLY_API_KEY` | *(optional)* | Tenderly API key for simulation |
| `TENDERLY_ACCOUNT` | `yearn` | Tenderly account slug |
| `TENDERLY_PROJECT` | `sam` | Tenderly project slug |

### Supported Providers

| Provider | Base URL | Default Model | Package |
|---|---|---|---|
| Venice.ai | `https://api.venice.ai/api/v1` | `grok-41-fast` | `openai` |
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-safeguard-20b` | `openai` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `openai` |
| Anthropic | *(native API)* | `claude-haiku-4-5-20251001` | `anthropic` |
| Custom | Set `LLM_BASE_URL` | Set `LLM_MODEL` | `openai` |

The `openai` and `anthropic` packages are optional dependencies. Install with:

```bash
uv pip install 'monitoring-scripts-py[ai]'
```

## Module Structure

```
utils/llm/
├── __init__.py              # Exports: LLMProvider, get_llm_provider
├── ai_explainer.py          # Orchestrator: decode → simulate → prompt → explain
├── anthropic_provider.py    # Anthropic (Claude) native API provider
├── base.py                  # Abstract LLMProvider base class + LLMError
├── factory.py               # Provider factory with env-based config + singleton
├── openai_compat.py         # OpenAI-compatible provider (Venice, OpenAI, etc.)
└── README.md                # This file
```

## Integration Points

- **Timelock alerts** (`timelock/timelock_alerts.py`): Calls `explain_transaction()` or `explain_batch_transaction()` for each scheduled operation
- **Safe alerts** (`safe/main.py`): Calls `explain_transaction()` for each pending Safe multisig transaction
- Both use `format_explanation_line()` to append the AI summary to Telegram messages
