# Morpho Monitoring

## Governance

For roles on morpho vaults check the following [document](https://github.com/morpho-org/metamorpho/blob/main/README.md).

## Monitoring

Morpho monitoring is define in [python script](./main.py) that is executed every hour using [Github Actions](../.github/workflows/hourly.yml).

The scripts checks if there are any new value pending in timelock for a given vault. Possible changes that can be detected are:

- Changing timelock value, minimal values is 1 day.
- Changing guardian address.
- Changing supply caps, only to higher value than the current one, for both supply and withdraw markets.
- Removing of a market from the vault.

### How to add a new vault

Add the vault address to variable `MAINNET_VAULTS` or `BASE_VAULTS` in the [python script](./main.py#L21).

## Bad Debt

Bad debt is fetch from Morpho graph API. Each of the used market is checked for bad debt, if any of the market has bad debt, telegram message is sent. The script is executed every hour using [Github Actions](../.github/workflows/hourly.yml).

### How to add a new market

Add the Morpho market address to variable `wanted_markets` in the [python script](./bad_debt.py#L12).

### Vault Risks

Nice read from Llama risk: [https://www.llamarisk.com/research/morpho-vaults-risk-disclaimer](https://www.llamarisk.com/research/morpho-vaults-risk-disclaimer)

## Risk Calculation

The total risk level of a vault is calculated as a weighted sum of market allocations and their risk tiers. Each market has a risk tier (1-5, with higher numbers indicating higher risk) that acts as a risk multiplier.

### Formula

```math
\text{Total Risk Level} = \sum_{i=1}^{n} (\text{Risk Tier}_i \times \text{Allocation}_i)
```

Where:

- `Risk Tier`: Market risk level (1-5)
- `Allocation`: Percentage of vault's assets in that market
- `Total Risk Level`: Sum of weighted risks across all markets

The calculated risk score is compared against maximum thresholds defined for each vault risk level:

- Risk Level 1: max 1.15
- Risk Level 2: max 2.20
- Risk Level 3: max 3.30
- Risk Level 4: max 4.40
- Risk Level 5: max 5.00

If a vault's total risk level exceeds its threshold, an alert is triggered and telegram message is sent.

## Market Allocation Monitoring

The system monitors individual market allocations within vaults to ensure they don't exceed risk-appropriate thresholds. Each market has a maximum allocation threshold based on its risk tier and the vault's risk level.

### Allocation Thresholds

Base allocation limits by risk tier:

- Risk Tier 1: 80%
- Risk Tier 2: 30%
- Risk Tier 3: 10%
- Risk Tier 4: 5%
- Risk Tier 5: 5%

### Threshold Adjustment

The actual threshold for a market is adjusted based on the vault's risk level. For higher vault risk levels, thresholds shift up (become more permissive). The adjustment is calculated as:

```python
adjusted_risk = max(1, market_risk_level - (vault_risk_level - 1))
threshold = ALLOCATION_TIERS[adjusted_risk]
```

For example:

- A Risk-2 market in a Risk-1 vault uses the 30% threshold
- The same Risk-2 market in a Risk-2 vault effectively becomes Risk-1, using the 80% threshold

### Alerts

The system continuously monitors the allocation ratio for each market:

```python
allocation_ratio = market_supply_usd / total_vault_assets_usd
```

If any market's allocation exceeds its adjusted threshold, an alert is triggered and telegram message is sent. This helps ensure that vaults maintain appropriate diversification and don't become overly concentrated in higher-risk markets.

## Markets

Risk level of the Morpho Vaults depends on the risk level of the markets used by the vault. For more information check comments for each market in [markets.py](./markets.py#L36). Markets are grouped by risk level and chain. Level 1 markets are safest.
