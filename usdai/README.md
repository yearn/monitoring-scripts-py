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
- **Mint Ratio**: The collateralization ratio retrieved from the protocol API (0.995).
- **Collateral**: Calculated as `USDai Supply / Mint Ratio`.
- **Buffer**: `Implied Collateral` - `USDai Supply`. A positive buffer indicates the system is functioning within the expected Mint Ratio parameters.

## Alerts

- **Buffer Drop**: A Telegram alert is triggered if the **Buffer** value decreases by more than **$10,000** from the last cached value. Since the buffer represents accumulated yield, it is expected to grow or remain stable. A significant drop could indicate:
  - A loss of backing value (depegging of underlying asset).
  - An issue with the yield accrual mechanism.
  - An unexpected withdrawal or rebalancing event.
- **Mint Ratio Change**: A Telegram alert is triggered if the protocol's Mint Ratio changes from its previous value. This is a critical parameter that determines backing requirements.
- **Governance Events**: We monitor for critical governance actions on the USDai Vault, USDai Token, and wM Token contracts, including:
  - Role Grants/Revocations (Access Control)
  - Contract Upgrades
  - Admin/Ownership Changes
  - Supply Cap Changes (`SupplyCapSet`)

## Contracts (Arbitrum One)

- **USDai Vault**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF`
- **wM Token**: `0x437cc33344a0b27a429f795ff6b469c72698b291`
- **sUSDai**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9`

## Governance & Security

- **Access Control**: The USDai token contract implements standard Access Control roles:
  - `DEFAULT_ADMIN_ROLE` (`0x00...`): Can grant and revoke other roles.
  - `hasRole(role, account)`: Used to verify permissions.
  - `getRoleAdmin(role)`: Determines who manages specific roles.
- **Upgradeability**:
  - **USDai Token**: Is an upgradeable contract (ERC1967Proxy). We monitor for `Upgraded` events.
  - **wM Token**: Is an upgradeable contract (ERC1967Proxy). We monitor for `Upgraded` events.
- **Functionality**:
  - **Supply Control**: Includes `supplyCap` and `totalSupply`.
  - **Bridging**: Includes `bridgedSupply` and `eip712Domain` (supports cross-chain/permit).
  - **Swap Adapter**: Contains a `swapAdapter` address for integrating swaps or redemptions.

## sUSDai FAQ

> **How does it work?**

**sUSDai** is a yield-bearing ERC-4626 vault token. It earns yield from M token emissions and by lending USDai to AI infrastructure pools (MetaStreet). It is not a stablecoin but a floating-price token representing a share of the lending portfolio and unallocated cash.

> **How to redeem it? Is there a queue?**

Redemption is done via the [app](https://app.usd.ai/unstake) or directly on-chain. It involves an **asynchronous request with a 30-day queue** (average wait expected to drop to 15 days). Redemptions are processed periodically by the protocol admin. Users wanting instant exit must use secondary markets (DEXs like Fluid/Curve), which currently hold ~$20M liquidity on Arbitrum.

> **Can it have losses?**

**Yes.** Unlike USDai (backed by T-Bills), sUSDai carries credit risk from its GPU-backed loans. If loans default and collateral liquidation is insufficient, the share price will drop, leading to principal loss. Redemptions use a "Conservative NAV" (Principal Only) to protect remaining stakers.

> **How is Price Per Share (PPS) defined? On-chain or Off-chain?**

**On-chain calculation using off-chain data.**
The contract calculates PPS on-chain (see `redemptionSharePrice`), but the underlying Net Asset Value (NAV) relies on off-chain loan health data. The system uses a dual-NAV model:

- **Optimistic NAV** (Principal + Interest) for Deposits.
- **Conservative NAV** (Principal Only) for Redemptions.
  A Chainlink oracle is used to convert pool positions into USDai value. Thus, while you can read the price on-chain, the inputs depend on the strategy's off-chain reporting.

## Usage

Collateral/Supply Monitoring:

```bash
uv run usdai/main.py
```

Governance Monitoring:

We monitor the USDai Admin Safe (`0xf223f...`) for queued transactions using the shared Safe monitoring script. This runs every 10 minutes via GitHub Actions.

```bash
# To run locally (checks all configured Safes)
uv run safe/main.py
```
