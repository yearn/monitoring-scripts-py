# Morpho Monitoring

## Governance

For roles on morpho vaults check the following [document](https://github.com/morpho-org/metamorpho/blob/main/README.md).

## Monitoring

Morpho monitoring is define in [python script](./main.py) that is executed every hour using [Github Actions](../.github/workflows/hourly.yml).

The scripts checks if there are any new value pending in timelock for a given vault. Possible changes that can be detected are:

- Changing timelock value, minimal values is 1 day.
- Changing guardian address.
- Changing supply caps for both supply and withdraw markets.

### How to add a new vault

Add the vault address to variable `MAINNET_VAULTS` or `BASE_VAULTS` in the [python script](./main.py).
