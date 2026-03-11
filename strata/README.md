# Strata Monitoring

Monitors core risk signals for Strata `srUSDe` and `jrUSDe` on Ethereum.

The script [`strata/main.py`](main.py) is designed to run hourly.

## What it checks

1. **Junior buffer vs senior TVL**
   - Uses `jr_assets / sr_assets` as a simple coverage proxy.
   - Alerts:
     - warning when ratio drops below `10%`
     - critical when ratio drops below `5%`

2. **srUSDe share value safety**
   - Monitors `srUSDe.convertToAssets(1e18)`.
   - Alerts if it decreases versus previous run.

3. **jrUSDe stress speed**
   - Alerts on fast jrUSDe share-value drops (>=2% since previous run).
   - Alerts on fast jrUSDe TVL drops (>=15% since previous run).

4. **USDe peg**
   - Pulls USDe price from DefiLlama.
   - Alerts:
     - warning at deviation >= `0.5%`
     - critical at deviation >= `2%`

## Contracts

- srUSDe: `0x3d7d6fdf07EE548B939A80edbc9B2256d0cdc003`
- jrUSDe: `0xC58D044404d8B14e953C115E67823784dEA53d8F`

## Governance monitoring

Governance is handled by existing shared monitors:

- Timelocks: `timelock/timelock_alerts.py`
- Multisigs: `safe/main.py`

Strata addresses for those are configured in those files.
