# Maker DAO

## Bad Debt

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.

## Governance

Tenderly alert for function [`plot()` called in DSPause](https://dashboard.tenderly.co/yearn/sam/alerts/rules/6c4b81c9-3130-4b3c-9356-15c9abc7b918) that schedules the plan (tx) that can be executed after a delay. A plan can be executed by anyone. A similar concept to Timelock controller. The minimum delay is set to [16 hours](https://etherscan.io/address/0xbe286431454714f511008713973d3b053a2d38f3#readContract#F2). Scheduled tx (spell) will only be executed Monday through Friday between 14:00 and 21:00 UTC.

[PauseProxy](https://etherscan.io/address/0xbe8e3e3618f7474f8cb1d074a26affef007e98fb) controls [PSM USDC](https://etherscan.io/address/0x89B78CfA322F6C5dE0aBcEecab66Aee45393cC5A#readContract#F9), it can update the DAI/USDC rate by calling the function `file()`. Its [owner is DSPause contract](https://etherscan.io/address/0xbe8e3e3618f7474f8cb1d074a26affef007e98fb#readContract#F1), any update is covered with Tenderly alert specified above.

Upgradeable [sUSDS](https://etherscan.io/address/0xa3931d71877c0e7a3148cb7eb4463524fec27fbd) contract owner is also [set](https://etherscan.io/tx/0x4d4a0396ac55bd2113fe630efe9db0330043508e19ed93d8bb3973a5dda3727e#eventlog) to DSPause contract. This is the some for upgradeable token [USDS](https://etherscan.io/address/0xdC035D45d973E3EC169d2276DDab16f1e407384F), tx owner [set](https://etherscan.io/tx/0x3c9a2a60285c972bf103d29ffe97503b25c5dbcb130f2bd862749a69ec21098c#eventlog).

To get the proposal data from the received alert:

1. see the tx from alert on [Tenderly](https://dashboard.tenderly.co/yearn/sam/tx/mainnet/0x4d84206c92894f4c4b5865d9c85f42105e5655d4a9415f799867a67ea3686c39)
2. get [DssSpell address](https://dashboard.tenderly.co/yearn/sam/tx/mainnet/0x4d84206c92894f4c4b5865d9c85f42105e5655d4a9415f799867a67ea3686c39?trace=0.1)
3. check proposals on [Maker DAO voting site](https://vote.makerdao.com/executive)
4. [match proposal with spell address](https://vote.makerdao.com/executive/template-executive-vote-lite-psm-usdc-a-phase-2-setup-august-22-2024) with DssSpell address from tx

Tenderly alert for [EOA wallet pocket](https://dashboard.tenderly.co/yearn/sam/alerts/rules/3fd3aa9f-5679-4f9d-8d58-a11c0439bd17) which holds USDC funds for PSM. It could remove approval for Maker LitePSM and break sUSDC strategy. This EOA is [Coinbase Web3 Wallet](https://forum.sky.money/t/litepsm-lite-psm-usdc-a-introduction-and-overview/24512).

[Governance DSPause module docs](https://docs.makerdao.com/smart-contract-modules/governance-module/pause-detailed-documentation).
