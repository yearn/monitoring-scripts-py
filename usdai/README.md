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
- **Loans**: Directly fetched from the Loan Router contract. Then calculated `Active loan amounts / total USDai supply`. to calculate the ratio.

## Alerts

- **Buffer Drop**: A Telegram alert is triggered if the **Buffer** value drops below $1M.
  A significant drop could indicate loss of backing value.
- **Loan Activity**: A Telegram alert is triggered if the **Total Verified Principal** changes (indicating a new loan origination or a repayment).
- **Legacy Loan Expiry**: A Telegram alert is triggered when the legacy loan (NVIDIA H200s) reaches its maturity date (July 2028).

- **Mint Ratio Change**: A Telegram alert is triggered if the protocol's Mint Ratio changes from its previous value. This is a critical parameter that determines backing requirements.
- **Governance Events**: We monitor for queued governance actions on the USDai Admin Safe and sUSDai Admin Safe contracts.

## Contracts (Arbitrum One)

- **USDai Token (Vault)**: `0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF`
- **wM Token**: `0x437cc33344a0b27a429f795ff6b469c72698b291`
- **sUSDai**: `0x0B2b2B2076d95dda7817e785989fE353fe955ef9`
- **Loan Router**: `0x0C2ED170F2bB1DF1a44292Ad621B577b3C9597D1`

## Tenderly Monitoring

The following addresses and events should be watched via Tenderly alerts:

1.  **Loan Router** (`0x0C2ED170F2bB1DF1a44292Ad621B577b3C9597D1`):
    - **Transfer**: Monitor for minting/burning of Loan NFTs.
    - **LoanOriginated** (or similar): Monitor for new GPU loan creation.

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

Collateral/Supply/Loan Monitoring:

```bash
uv run usdai/main.py
```

### Loan Calculation Methodology

The script calculates GPU loans by directly scanning the **Loan Router** contract for active loan NFTs held by the sUSDai Vault.

1. **Direct Read**: It scans `tokenOfOwnerByIndex` on the Loan Router for the sUSDai address.
2. **Decoding**: It decodes the raw `loanState` storage to extract the exact **Principal Amount** and **Maturity Date**.
3. **Legacy Loans**: It includes hardcoded values for known legacy loan (NVIDIA H200s, $560k) that originated before the current Loan Router deployment.
4. **Total Principal**: Sums these up to track the exact face value of active loans.

Governance Monitoring:

We monitor the following Safes for queued transactions using the shared Safe monitoring script:

- **USDai Admin Safe**: [`0xF223F...`](https://arbiscan.io/address/0xF223F8d92465CfC303B3395fA3A25bfaE02AED51) (2/4 multisig) - Admin of wM Token.
- **sUSDai Admin Safe**: [`0x783B...`](https://arbiscan.io/address/0x783B08aA21DE056717173f72E04Be0E91328A07b) (3/3 multisig) - Admin of USDai Token (Vault) and sUSDai.

This runs every 10 minutes via GitHub Actions.

```bash
uv run safe/main.py
```
