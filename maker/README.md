# Maker DAO

## Governance

### Proposals Script

`proposals.py` monitors new executive proposals from the [Sky governance portal](https://vote.sky.money/executive) using the public API at `https://vote.sky.money/api/executive`. Sends Telegram alerts for new proposals and caches the last seen proposal timestamp to avoid duplicate messages.

Run: `python maker/proposals.py`

### DSPause Timelock

[DSPause](https://etherscan.io/address/0xbe286431454714f511008713973d3b053a2d38f3) schedules spells via `plot()` that can be executed after a delay. The minimum delay is [16 hours](https://etherscan.io/address/0xbe286431454714f511008713973d3b053a2d38f3#readContract#F2). Scheduled spells will only be executed Monday through Friday between 14:00 and 21:00 UTC.

Monitored via the internal [timelock monitoring system](../timelock/README.md) (`MAKER` protocol). Alerts are sent to the Maker Telegram channel when `plot()` is called.

[PauseProxy](https://etherscan.io/address/0xbe8e3e3618f7474f8cb1d074a26affef007e98fb) controls [PSM USDC](https://etherscan.io/address/0x89B78CfA322F6C5dE0aBcEecab66Aee45393cC5A#readContract#F9), it can update the DAI/USDC rate by calling the function `file()`. Its [owner is DSPause contract](https://etherscan.io/address/0xbe8e3e3618f7474f8cb1d074a26affef007e98fb#readContract#F1), any update is covered by the timelock alert.

Upgradeable [sUSDS](https://etherscan.io/address/0xa3931d71877c0e7a3148cb7eb4463524fec27fbd) contract owner is also [set](https://etherscan.io/tx/0x4d4a0396ac55bd2113fe630efe9db0330043508e19ed93d8bb3973a5dda3727e#eventlog) to DSPause contract. This is the same for upgradeable token [USDS](https://etherscan.io/address/0xdC035D45d973E3EC169d2276DDab16f1e407384F), tx owner [set](https://etherscan.io/tx/0x3c9a2a60285c972bf103d29ffe97503b25c5dbcb130f2bd862749a69ec21098c#eventlog).

[Governance DSPause module docs](https://docs.makerdao.com/smart-contract-modules/governance-module/pause-detailed-documentation).

## PSM Balance

Tenderly alert for [PSM balance](https://dashboard.tenderly.co/yearn/sam/alerts/rules/4033c908-e924-43c1-a12c-5be712c039d8) of USDC. If the balance is less than 2B USDC, telegram alert is sent Maker DAO channel. On 5th March 2026, the balance was 4.46B USDC, [PSM contract](https://etherscan.io/address/0x37305B1cD40574E4C5Ce33f8e8306Be057fD7341#readContract).
