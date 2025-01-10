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

### Risks

Nice read from Llama risk: [https://www.llamarisk.com/research/morpho-vaults-risk-disclaimer](https://www.llamarisk.com/research/morpho-vaults-risk-disclaimer)
