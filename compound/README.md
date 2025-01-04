# Compound V3

## Bad Debt

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.

## Utilization

Github actions run hourly and send telegram message if there is a market with utilization above `99%`. [Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/compound/main.py).

## Governance

Tenderly alert for queueing tx to [Timelock contract on Mainnet](https://dashboard.tenderly.co/yearn/sam/alerts/rules/e978ddbe-5631-424d-bead-54079286e5e5).

This Timelock contract covers **Mainnet and all other chains**. Each protocol contract is controlled by the [Timelock contract](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#code). For more info see the [governance docs](https://docs.compound.finance/governance/). Delay is [2 days](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#readContract).

Additionally, Github actions bot runs every hour and fetches queued proposals using Compound API: https://github.com/tapired/monitoring-scripts-py/blob/main/compound/proposals.py
