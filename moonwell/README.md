# Moonwell

[Moonwell](https://moonwell.fi/) is Compound V2 fork.

## Bad Debt

TODO: implement using this site: https://defirisk.intotheblock.com/metrics/base/moonwell or https://app.gauntlet.xyz/protocols/moonwell/markets/base/liquidations

## Utilization

TODO: check if it possible to use the data from this website: https://app.gauntlet.xyz/protocols/moonwell/markets/base

## Governance

Tenderly alert for queueing tx to [Timelock contract on Base](https://dashboard.tenderly.co/yearn/sam/alerts/rules/41361042-facb-4d5d-b4a5-ddd1323e0602).

[Comptroller contract](https://docs.moonwell.fi/moonwell/developers/comptroller) which handles upgrades and config updates is controlled by the [Timelock contract](https://basescan.org/address/0xfbb21d0380bee3312b33c4353c8936a0f13ef26c#readProxyContract#F2). Delay is [1 day](https://basescan.org/address/0x8b621804a7637b781e2BbD58e256a591F2dF7d51#readContract#F10). The Timelock contract can be paused by the [owner](https://basescan.org/address/0x8b621804a7637b781e2BbD58e256a591F2dF7d51#readContract#F7), which is multisig monitored by our bot.

To get the proposal data from the received alert:

1. see the tx from alert on [Tenderly](https://dashboard.tenderly.co/yearn/sam/tx/base/0x43f11101683eb6d58d346cc0f1c810f66abd1979539b0b54170904e5af64a310)
2. find the event `ProposalStateChanged` and get [`proposalId` value](https://basescan.org/tx/0x43f11101683eb6d58d346cc0f1c810f66abd1979539b0b54170904e5af64a310#eventlog)
3. go to Moonwell governance [https://moonwell.fi/governance/proposal/moonbeam?id=proposalId+79](https://moonwell.fi/governance/proposal/moonbeam?id=147) and check the proposal data. For base, the proposalId is increased by 79.

TODO: Add API calls to get governance proposals.
