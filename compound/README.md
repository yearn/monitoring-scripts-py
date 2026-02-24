# Compound V3

## Utilization

Github actions run hourly and send telegram message if there is a market with utilization above `99%`. [Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/compound/main.py).

## Governance

[Internal timelock monitoring](../timelock/README.md) for queueing tx to [Timelock contract on Mainnet](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#code).

This Timelock contract covers **Mainnet and all other chains**. Each protocol contract is controlled by the [Timelock contract](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#code). For more info see the [governance docs](https://docs.compound.finance/governance/). Delay is [2 days](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#readContract).

Additionally, Github actions bot runs every hour and fetches queued proposals using Compound API: https://github.com/tapired/monitoring-scripts-py/blob/main/compound/proposals.py

## Data Monitoring

The script [markets.py](markets.py) is run hourly by Github actions. It fetches the data from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler) and sends alerts if the thresholds are exceeded.

### Debt Supply Ratio

The script fetches the data from [Gauntlet dashboard](https://dashboards.gauntlet.xyz/protocols/euler) and sends alerts if the debt supply ratio is greater than 60%.

## Vaults & Markets

Euler Markets consist of multiple vaults, each defining key parameters such as LTV, interest rate models, and oracle data. Euler Vaults contains only one asset, meaning `vault=asset` plus risk configuration.

> Euler Market is similar to Morpho Vault. Euler Vault is similar to Morpho Market but it is only for one token, has its own IRM and risk parameters.

Vaults monitoring is configured by defining wanted markets to monitor in [`COMPOUND_VAULTS_KEYS`](./main.py#24). The script fetches vaults/assets for each market and checks the following metrics:

- **Vault Risk Level:** If the computed risk level of a vault exceeds its maximum threshold, a Telegram message is sent.
- **Vault Allocation Ratio:** If any vaults's allocation ratio exceeds its risk-adjusted threshold, a Telegram message is sent.

### Risk Levels

The overall risk level of a Euler Market is determined by the risk levels of its vaults. For more details about the risk levels of each vault/asset, refer to the comments in [SUPPLY_ASSETS](/utils/gauntlet.py#L7). Markets and vaults are categorized by their risk level and blockchain, with Level 1 representing the safest configuration.

### How to Add a New Market

To monitor a new market, add its address and risk level to the `COMPOUND_VAULTS_KEYS` variable in [markets.py](./main.py#24). This ensures that both the vault's overall metrics and its individual markets are monitored. Also, add each vault to `SUPPLY_ASSETS` variable in [markets.py](/utils/gauntlet.py#L7). If the vault score is not added, maximum risk level 5 is used.

### Market Risk Level

The total risk level of a market is computed as the weighted sum of the risk levels of its individual market allocations:

```math
\text{Total Risk Level} = \sum_{i=1}^{n} (\text{Vault Risk Level}_i \times \text{Allocation}_i)
```

Where:

- **Vault Risk Level:** A value between 1 and 5, with 1 representing the lowest risk. This value acts as a multiplier (e.g., a market with risk level 1 contributes a multiplier of 1, level 2 contributes 2, etc.).
- **Allocation:** The percentage of the vault's assets allocated to that market.
- **Total Risk Level:** The sum of the weighted risks across all vaults.

This computed risk level is compared against predefined maximum thresholds defined in [MAX_RISK_THRESHOLDS](/utils/gauntlet.py#L88):

- **Risk Level 1:** Maximum threshold of 1.10
- **Risk Level 2:** Maximum threshold of 2.20
- **Risk Level 3:** Maximum threshold of 3.30
- **Risk Level 4:** Maximum threshold of 4.40
- **Risk Level 5:** Maximum threshold of 5.00

If a vault's total risk level exceeds its threshold, an alert is triggered via a Telegram message.

### Vault/Asset Allocation Ratio

The system monitors each vaults/assets allocation within a market to ensure it does not exceed its risk-adjusted threshold. Each vault/asset has a maximum allocation threshold based on its inherent risk tier and the market's overall risk level.

The base allocation limits by risk tier (as defined in [ALLOCATION_TIERS](/utils/gauntlet.py#L79)) are:

- **Risk Level 1:** 100%
- **Risk Level 2:** 30%
- **Risk Level 3:** 10%
- **Risk Level 4:** 5%
- **Risk Level 5:** 1%

These limits apply to markets with a risk level of 1. For markets with higher risk levels, the thresholds become more permissive. The adjustment is calculated in the [get_market_allocation_threshold](/utils/gauntlet.py#L208) function.

Examples:

- A Risk-1 market accepts up to 30% of its total assets in a Risk-2 vault/asset.
- A Risk-2 market accepts up to 80% of its total assets in a Risk-2 vault.
- A Risk-3 market accepts up to 100% of its total assets in a Risk-2 vault.
- A Risk-2 market accepts up to 10% of its total assets in a Risk-4 vault.
- A Risk-3 market accepts up to 30% of its total assets in a Risk-4 vault.

The system monitors the allocation ratio for each market hourly:

```math
\text{Allocation\_ratio} = \frac{\text{Market Supply USD}}{\text{Total Vault Assets USD}}
```

If any asset allocation exceeds its adjusted threshold, an alert is triggered with a corresponding Telegram message. This mechanism ensures that markets maintain proper diversification and are not overly concentrated in higher-risk vaults.

### Bad Debt

> NOTE: Disabled because Risk DAO is not serving the data anymore.

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.
