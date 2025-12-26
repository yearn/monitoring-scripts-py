# USDai Monitoring

This script monitors the USDai protocol on Arbitrum One, specifically the relationship between its supply and collateral backing.

## Protocol Overview

- **Docs**: [Proof of Reserves Guide](https://docs.usd.ai/app-guide/proof-of-reserves)
- **Claimed Backing**: [99.8% by TBills](https://app.usd.ai/reserves)
- **Mechanism**: USDai is backed by `wM` (Wrapped M) tokens. `M` is a token representing T-Bill yields from the M^0 protocol.
- **Backing Source**: The M^0 protocol backs `M` tokens with off-chain T-Bills held in custody. `wM` is a wrapper that enables `M` to be used on other chains like Arbitrum, rebasing or accumulating value to reflect T-Bill yield.
- **Minting**: Minting involves depositing `wM` into the USDai Vault, which ensures 1:1 backing for the minted `USDai`.

## Metrics & Monitoring

We track the following key metrics to ensure solvency and stability:

- **USDai Supply**: The calculated supply based on the `wM` balance held by the USDai Vault on-chain.
- **Mint Ratio**: The collateralization ratio retrieved from the protocol API (e.g., 0.9950).
- **Implied Collateral**: Calculated as `USDai Supply / Mint Ratio`.
- **Buffer**: `Implied Collateral` - `USDai Supply`. A positive buffer indicates the system is functioning within the expected Mint Ratio parameters.

## Alerts

- **Buffer Drop**: A Telegram alert is triggered if the **Buffer** value decreases by more than **$1,000** from the last cached value. Since the buffer represents accumulated yield, it is expected to grow or remain stable. A significant drop could indicate:
  - A loss of backing value (depegging of underlying asset).
  - An issue with the yield accrual mechanism.
  - An unexpected withdrawal or rebalancing event.
- **Governance Events**: We monitor for critical governance actions on the USDai Vault, USDai Token, and wM Token contracts, including:
  - Role Grants/Revocations (Access Control)
  - Contract Upgrades
  - Admin/Ownership Changes

## Contracts (Arbitrum One)

- **USDai Vault**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF`
- **wM Token**: `0x437cc33344a0b27a429f795ff6b469c72698b291`

## Governance & Security

- **Access Control**: The USDai token contract implements standard Access Control roles:
  - `DEFAULT_ADMIN_ROLE` (`0x00...`): Can grant and revoke other roles.
  - `hasRole(role, account)`: Used to verify permissions.
  - `getRoleAdmin(role)`: Determines who manages specific roles.
- **Upgradeability**:
  - The USDai contract includes `IMPLEMENTATION_VERSION` (currently `1.3`), indicating it is likely an upgradeable contract (e.g., UUPS or Transparent Proxy pattern).
  - The `wM` token contract constructor references a `migrationAdmin`, suggesting potential upgrade or migration capabilities.
- **Functionality**:
  - **Supply Control**: Includes `supplyCap` and `totalSupply`.
  - **Bridging**: Includes `bridgedSupply` and `eip712Domain` (suggesting cross-chain or permit capabilities).
  - **Swap Adapter**: Contains a `swapAdapter` address, likely for integrating swaps or redemptions.

## Usage

Collateral/Supply Monitoring:

```bash
uv run usdai/main.py
```

Governance Monitoring:

```bash
uv run usdai/governance.py
```
