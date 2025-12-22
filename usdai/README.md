# USDai Monitoring

This script monitors the USDai protocol on Arbitrum One, tracking its collateral backing and governance changes.

## Protocol Overview

- **Docs**: [Proof of Reserves Guide](https://docs.usd.ai/app-guide/proof-of-reserves)
- **Claimed Backing**: [99.8% by TBills](https://app.usd.ai/reserves)
- **Mechanism**: USDai is backed by `wM` (Wrapped M) tokens. `M` is a token representing T-Bill yields. The protocol uses a "Vault" contract to hold `wM` reserves against the `USDai` supply.
- **TBills Backing**: Provided via the `M` token (M^0 protocol), which is backed by off-chain T-Bills. `wM` wraps this exposure.
- **Minting**: Minting logic is controlled by the `wM` and `M` token interactions, with the Vault ensuring backing.

## Metrics & Monitoring

We track the following on-chain metrics to verify backing:

- **USDai Supply**: Calculated as the `wM` balance held by the USDai Vault (`0x0A...82EF`). This proxies the circulating supply as the Vault ensures 1:1 backing.
- **TBILL BACKING**: Derived as: `Total wM Supply` - `sUSDai wM Holdings`. This isolates the `wM` backing available specifically for `USDai` (excluding the staked portion `sUSDai`).
- **Buffer**: `TBILL BACKING` - `USDai Supply`. Represents the excess collateral.
- **Ratio**: `TBILL BACKING` / `USDai Supply`.

## Alerts

- **Ratio Swing**: Triggers a Telegram alert if the Ratio drops by **0.05%** or more from the last cached value.

## Contracts (Arbitrum One)

- **USDai Vault**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF`
- **wM Token**: `0x437cc33344a0b27a429f795ff6b469c72698b291`
- **sUSDai**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9`

## Usage

```bash
uv run python3 usdai/main.py
```
