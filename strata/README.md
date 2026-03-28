# Strata Monitoring

Monitors Strata srUSDe/sUSDe risk and governance signals on Ethereum.

## Scope

### srUSDe Vault Monitoring
- srUSDe: `0x3d7d6fdf07EE548B939A80edbc9B2256d0cdc003`
- Monitor `convertToAssets(1e18)`; alert if exchange rate decreases.
- Monitor `Deposit` and `Withdraw` events:
  - alert for flows `>$1M`
  - whale alert for single flow `>$5M`

### StrataCDO Monitoring
- StrataCDO: `0x908B3921aaE4fC17191D382BB61020f2Ee6C0e20`
- Monitor senior coverage ratio; alert if ratio is below `105%`.
- Watch junior side draining via `jrUSDe.totalAssets()` rapid drop.
- Monitor pausing actions (`setActionStates`) via timelock scheduled-call decoding.

### Strategy Monitoring
- sUSDeStrategy: `0xdbf4FB6C310C1C85D0b41B5DbCA06096F2E7099F`
- Monitor `sUSDe` balance held by strategy.
- Alert if strategy balance drops significantly relative to total deposits.

### Governance Monitoring
- Admin Multisig: `0xA27cA9292268ee0f0258B749f1D5740c9Bb68B50`
- 48h Timelock: `0xb2A3CF69C97AFD4dE7882E5fEE120e4efC77B706`
- 24h Timelock: `0x4f2682b78F37910704fB1AFF29358A1da07E022d`
  - monitor `CallScheduled`, `CallExecuted`, `Cancelled`
  - immediate alert on `CallScheduled`

### Ethena Dependency Monitoring
- USDe peg:
  - warning alert if deviation `>0.5%`
  - critical alert if deviation `>2%`
- sUSDe vault anomalies:
  - monitor `convertToAssets(1e18)` monotonicity
  - monitor cooldown period changes

## Frequency
- Timelock scheduled calls: near real-time (10-minute cadence, `multisig-checker.yml`)
- Proxy upgrade events: near real-time via safe/timelock queue monitoring (`multisig-checker.yml`)
- srUSDe exchange rate: daily (`daily.yml`)
- Senior coverage ratio: daily (`daily.yml`)
- USDe peg stability: hourly (`hourly.yml`)
- Strategy sUSDe balance: daily (`daily.yml`)
- Protocol TVL changes: daily (`daily.yml`)
