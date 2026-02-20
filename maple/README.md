# Maple Finance syrupUSDC Monitoring

## What it monitors

- **PPS (Price Per Share):** Tracks `convertToAssets(1e6)` on the syrupUSDC pool. Should be monotonically increasing. Alerts on any decrease, which would indicate loan impairment or loss.
- **TVL (Total Value Locked):** Monitors `totalAssets()`. Alerts on changes exceeding 15% between runs.
- **Unrealized Losses:** Checks both FixedTermLoanManager and OpenTermLoanManager for non-zero `unrealizedLosses()`. Any non-zero value indicates an active loan impairment.
- **Strategy Allocations:** Tracks `assetsUnderManagement()` on Aave and Sky strategy contracts for DeFi allocation visibility.
- **Withdrawal Queue vs Liquid Funds:** Alerts when pending withdrawal shares reach 20% of liquid funds (Aave + Sky strategy AUM).

## Key Contracts

| Contract | Address | Purpose |
|----------|---------|---------|
| syrupUSDC Pool | [`0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b`](https://etherscan.io/address/0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b) | ERC-4626 vault |
| FixedTermLoanManager | [`0x4A1c3F0D9aD0b3f9dA085bEBfc22dEA54263371b`](https://etherscan.io/address/0x4A1c3F0D9aD0b3f9dA085bEBfc22dEA54263371b) | Loan health |
| OpenTermLoanManager | [`0x6ACEb4cAbA81Fa6a8065059f3A944fb066A10fAc`](https://etherscan.io/address/0x6ACEb4cAbA81Fa6a8065059f3A944fb066A10fAc) | Loan health |
| AaveStrategy | [`0x560B3A85Af1cEF113BB60105d0Cf21e1d05F91d4`](https://etherscan.io/address/0x560B3A85Af1cEF113BB60105d0Cf21e1d05F91d4) | DeFi allocation |
| SkyStrategy | [`0x859C9980931fa0A63765fD8EF2e29918Af5b038C`](https://etherscan.io/address/0x859C9980931fa0A63765fD8EF2e29918Af5b038C) | DeFi allocation |
| WithdrawalManagerQueue | [`0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3`](https://etherscan.io/address/0x1bc47a0Dd0FdaB96E9eF982fdf1F34DC6207cfE3) | Withdrawal processing |

## Alert Thresholds

| Metric | Threshold | Severity |
|--------|-----------|----------|
| PPS decrease | Any decrease | Critical |
| TVL change | >15% between runs | Warning |
| Unrealized losses | Any non-zero | Critical |
| Withdrawal queue | >=20% of liquid funds | Warning |

## Governance Monitoring

- **DAO Multisig** ([`0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196`](https://etherscan.io/address/0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196)): Added to [safe monitoring](../safe/README.md). Alerts on queued multisig transactions.
- **Governor Timelock** ([`0x2eFFf88747EB5a3FF00d4d8d0f0800E306C0426b`](https://etherscan.io/address/0x2eFFf88747EB5a3FF00d4d8d0f0800E306C0426b)): Should be added to [cross-protocol timelock monitoring](../timelock/README.md).

## Running

```bash
uv run maple/main.py
```

## Frequency

Runs hourly via [GitHub Actions](../.github/workflows/hourly.yml).

## Risk Report

Full risk assessment: [maple-syrupusdc report](https://github.com/tapired/risk-score/blob/master/reports/report/maple-syrupusdc.md)
