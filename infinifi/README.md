# Infinifi Protocol Monitoring

This folder contains monitoring scripts for the Infinifi protocol.

## Structure

- `main.py`: Monitors protocol reserves, backing, and liquid USDC reserves.
  Run this script hourly using github actions.

[Risk Score Report](https://github.com/yearn/risk-score/blob/master/reports/report/infinifi.md)

## Alerts

- **Liquid Reserves**: A Telegram alert is triggered if liquid reserves drop below $15M.
- **Reserve Ratio Breach**: Alert if liquid ratio falls below protocol `reserveRatio` target.
- **Illiquid Ratio Breach**: Alert if illiquid ratio rises above protocol `illiquidTargetRatio`.
- **Backing Per iUSD**: Alert if `totalTVL / iUSD supply` drops below `0.999`.
- **Redemption Pressure**: Alert if `pending redemptions / liquid reserves` exceeds `80%`.
- **Farm Allocation Shift**: Alert if any farm allocation ratio (`farm assets / total TVL`) changes by more than `FARM_RATIO_CHANGE_ALERT_THRESHOLD` versus cached ratio.
- **Farm Activation**: Alert if a farm previously at `0` cached ratio moves above `FARM_RATIO_ACTIVATION_ALERT_THRESHOLD` of total TVL.

## Governance Monitoring

Governance monitoring will be monitored via Tenderly alerts on the following addresses:

**Team Multisig**:

- `0x80608f852D152024c0a2087b16939235fEc2400c`

**Timelock Contracts**:

- `TIMELOCK_SHORT`: `0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32`
- `TIMELOCK_LONG`: `0x3D18480CC32B6AB3B833dCabD80E76CfD41c48a9`

**Deployer Address**:

- `0xdecaDAc8778D088A30eE811b8Cc4eE72cED9Bf22`

## Resources

- [Docs](https://docs.infinifi.xyz/)
- iUSD Token: 0x48f9e38f3070AD8945DFEae3FA70987722E3D89c (Ethereum)
- [Protocol Analytics](https://stats.infinifi.xyz/)
