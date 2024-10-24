# SAM Tools

The list of monitoring tools for the following protocols

## Aave V3

### Bad Debt

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.

### Utilization

Github actions run hourly and send telegram message if there is a market with utilization above `96%`. [Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/aave/main.py).

### Governance

Tenderly alert for [queueing proposal to Aave Governance contract](https://dashboard.tenderly.co/yearn/sam/alerts/rules/eae36bdd-b44c-45d5-acf7-b013238e32c0).
Proposal can be executed immediately because the cooldown period is [set to 0](https://etherscan.io/address/0x9aee0b04504cef83a65ac3f0e838d0593bcb2bc7#readProxyContract#F3). After the proposal is executed, the payload is queued to Payload Controller which has min execution delay [set to 1 day](https://etherscan.io/address/0xdabad81af85554e9ae636395611c58f7ec1aaec5#readProxyContract#F6).
Every payload that is executed on any network is the first queue to proposal on the mainnet. Monitoring just the proposal queue on the mainnet enables to get notification for future updates on all networks.

Additionally, Github actions bot runs every hour and fetches queued proposals using The Graph data: https://github.com/tapired/monitoring-scripts-py/blob/main/aave/proposals.py

Monitoring Safe multisigs of Protocol emergency Guardian and Governance emergency Guardian. Link with [address](https://app.aave.com/governance/v3/proposal/?proposalId=184) and [explanation](https://governance.aave.com/t/arfc-renewal-of-aave-guardian-2024/17523).

### External Monitoring

ChaosLabs has a public Telegram group with alerts for Aave V3: https://community.chaoslabs.xyz/aave/risk/alerts

## Compound V3

### Bad Debt

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.

### Utilization

Github actions run hourly and send telegram message if there is a market with utilization above `96%`. [Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/compound/main.py).

### Governance

Tenderly alert for queueing tx to [Timelock contract on Mainnet](https://dashboard.tenderly.co/yearn/sam/alerts/rules/e978ddbe-5631-424d-bead-54079286e5e5).

This Timelock contract covers **Mainnet and all other chains**. Each protocol contract is controlled by the [Timelock contract](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#code). For more info see the [governance docs](https://docs.compound.finance/governance/). Delay is [2 days](https://etherscan.io/address/0x6d903f6003cca6255D85CcA4D3B5E5146dC33925#readContract).

Additionally, Github actions bot runs every hour and fetches queued proposals using Compound API: https://github.com/tapired/monitoring-scripts-py/blob/main/aave/proposals.py

## Euler

### Governance

Github actions bot that check every hour if there are queued transactions in [Safe Multisig (4/7)](https://app.safe.global/transactions/queue?safe=eth%3A0xcAD001c30E96765aC90307669d578219D4fb1DCe). Sends telegram message for new queued transactions.

## Maker DAO

### Bad Debt

[Github actions bot](https://github.com/tapired/monitoring-scripts-py/blob/main/.github/workflows/bad-debt.yml) for bad debt in the protocol. Uses [Risk DAO](https://bad-debt.riskdao.org/) data. Sends telegram message if the bad debt ratio is above `0.1%`.

### Governance

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

## Lido

### Governance

Tenderly alerts will send telegram message when there are transactions made by:

- [Lido DAO voting](https://dashboard.tenderly.co/yearn/sam/alerts/rules/8e577a18-92b2-4cab-86b8-53c7c3025a00) which start the voting process. The alert is triggered on event emitted `StartVote` to cover both `newVote()` functions for starting the voting process. Voted transactions(script) can be forwarded to [Lido DAO Aragon Agent](https://etherscan.io/address/0x3e40D73EB977Dc6a537aF587D48316feE66E9C8c) for execution. Aragon Agent contract can update the following proxies:
  - [Locator proxy](https://etherscan.io/address/0xC1d0b3DE6792Bf6b4b37EccdcC24e45978Cfd2Eb#readContract#F1) - is the universal address book for the Lido protocol. All addresses are embedded into the implementation's bytecode as immutables for gas efficiency, allowing one to update them along with a proxy implementation. [Docs](https://docs.lido.fi/contracts/lido-locator)
  - [Staking router proxy](https://etherscan.io/address/0xFdDf38947aFB03C621C71b06C9C70bce73f12999#readContract#F1) - is a top-level controller contract for staking modules. Used to maintain a registry of staking modules, allocating stake to modules, and distribute protocol fees. [Docs](https://docs.lido.fi/contracts/staking-router)
  - [Withdrawal queue ERC721 proxy](https://etherscan.io/address/0x889edC2eDab5f40e902b864aD4d7AdE8E412F9B1#readContract#F1) - A FIFO queue for stETH withdrawal requests and an unstETH NFT implementation representing the position in the queue. [Docs](https://docs.lido.fi/contracts/withdrawal-queue-erc721/).

Monitor Safe multisig for [Emergency Brakes functions](https://docs.lido.fi/multisigs/emergency-brakes/):

- Emergency Brakes: Ethereum used to disable deposits & withdrawals for wstETH bridging to other chains (Arbitrum, Optimism, Base, Scroll, Mantle, ZKSync, Binance Smart Chain, Mode) in case of an emergency on Ethereum mainnet or the counterpart chain, and can pause Easy Track pipeline.
- GateSeal Committee - can trigger GateSeal to pause WithdrawalQueueERC721. Expires on 1 April 2025.

Not monitoring [Easy track voting](https://docs.lido.fi/guides/easy-track-guide/) because it cannot trigger crucial changes. Responsible only for:

- Node Operators increasing staking limits
- Funds being allocated to LEGO program
- Funds being allocated to reward programs

### Exchange rates

Sending telegram message if the exchange rate on DEX is above [defined threshold](https://github.com/tapired/monitoring-scripts-py/blob/main/lido/steth/main.py#L7)`5%` from validator rate.

- stETH: [Curve pool](https://curve.fi/#/ethereum/pools/steth/deposit) - [0xDC24316b9AE028F1497c275EB9192a3Ea0f67022](https://etherscan.io/address/0xDC24316b9AE028F1497c275EB9192a3Ea0f67022)
- stMatic: [Balancer pool](https://balancer.fi/pools/polygon/v2/0xf0ad209e2e969eaaa8c882aac71f02d8a047d5c2000200000000000000000b49)

[Python script code](https://github.com/tapired/monitoring-scripts-py/tree/main/lido)

## Stargate

### Withdraw amount

Github bot that triggers every hour to check the amount of withdroom room. Telegram message is sent if the withdroom below the amount deposited by the strategy.
Setup for:

- Polygon:
  - yearn-V3-Stargate-DAI
  - yearn-V3-Stargate-USDT
  - yearn-V3-Stargate-USDC
- Arbitrum:
  - yearn-V3-Stargate-USDT
  - yearn-V3-Stargate-USDC.E

[Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/stargate/main.py)

This bot is suspended because Stargate strategies are not active or have minimal amounts.

### Governance

Stargate contracts are controlled by a Safe Multisig (3/6). Github actions run hourly and send telegram message when there is a queued transaction in Safe Multisig.

These multisigs have the ability to add or remove bridge assets, configure bridge parameters and STG emissions, adjust pool parameters such as deposit fees when minting liquidity on Stargate pools, and execute emergency functions in bridge contracts.

    Mainnet Safe Multisig: 0x65bb797c2B9830d891D87288F029ed8dACc19705
    Polygon Safe Multisig: 0x47290DE56E71DC6f46C26e50776fe86cc8b21656
    Optimism Safe Multisig: 0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43
    Arbitrum Safe Multisig: 0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d

## Silo

### Bad Debt

Github actions run hourly and send telegram message if there are positions with `riskFactor > 1` which can lead to bad debt.
[Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/silo/main.py)

### Governance

- [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/363c626b-2249-4d51-bad8-40cc92b58f24) to send Telegram message for scheduled transactions in Timelock controller. Min delay is set to [2 days](https://etherscan.io/address/0xe1F03b7B0eBf84e9B9f62a1dB40f1Efb8FaA7d22#readContract#F5).
- Github actions run hourly and send telegram message when there are queued transactions in Safe Multisig (3/6).

Important contracts such as SiloRepository and SiloRouter are owned by the Safe Multisigs listed below, and we monitor the pending transactions of these multisigs every hour. In the future, SILO will transition to on-chain voting with the Timelock contract and veSILO. Details can be found [here](https://gov.silo.finance/t/silo-finance-2024-roadmap/451).

Currently, there is a [Timelock contract](0xe1F03b7B0eBf84e9B9f62a1dB40f1Efb8FaA7d22) deployed. However, it does not own any of the important contracts as the transition to complete on-chain governance is not yet complete.

    Mainnet Safe Multisig: 0xE8e8041cB5E3158A0829A19E014CA1cf91098554
    Optimism Safe Multisig: 0x468CD12aa9e9fe4301DB146B0f7037831B52382d
    Arbitrum Safe Multisig: 0x865A1DA42d512d8854c7b0599c962F67F5A5A9d9

## Spark

### Utilization

Github actions run hourly and send telegram message if there is a market with utilization above 95%. [Python script code](https://github.com/tapired/monitoring-scripts-py/blob/main/spark/main.py).

Possible improvements: add bad debt to risk dao and trigger telegram bot if there is some. Add governance part after the End Game.

## Pendle

### Governance

Pendle's important contracts are owned by a 2/4 Safe Multisig on each network. These multisigs are responsible for adding new facets to the Pendle router and configuring the yield factories. While the already deployed PT, YT, and markets are not owned by these multisigs, the SY tokens are, and these tokens are upgradable with a pause functionality that the multisigs can trigger.

Additionally, other contracts like vePENDLE, PENDLE, RewardDistributor, and Voting are also owned by these multisigs, allowing them to change parameters and trigger emergency functions within these contracts.

    Mainnet Safe Multisig: 0x8119EC16F0573B7dAc7C0CB94EB504FB32456ee1
    Arbitrum Safe Multisig: 0x7877AdFaDEd756f3248a0EBfe8Ac2E2eF87b75Ac

The owner of SY contracts was changed to [governance proxy contract](https://etherscan.io/address/0x2aD631F72fB16d91c4953A7f4260A97C2fE2f31e) with an additional guardian role that can only pause SY contracts. The governance proxy contract owner is multisig defined above.

## LRT Pegs

### Exchange rates

Checks the main liquidity pools of LRTs to detect depegging, such as the ezETH-WETH and rsETH-WETH pools in Balancer. The bot monitors pool balances and sends a message if they become skewed.
