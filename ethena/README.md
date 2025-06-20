# Ethena

## Overview

Ethena is a synthetic dollar protocol built on Ethereum that provides a crypto-native solution for money, USDe, alongside a globally accessible dollar savings asset, sUSDe.

## Monitoring

The script [`ethena/ethena.py`](ethena.py) runs **hourly via GitHub Actions** to sanity-check that **USDe remains fully backed** and that the public data feeds are fresh and internally consistent.
Data used is provided by Ethena on [transparency page](https://app.ethena.fi/dashboards/transparency).

### Data Sources

1. **Ethena Transparency**
   • Collateral: `GET /positions/current/collateral?latest=true`
   • Supply  : `GET /solvency/token-supply?symbol=USDe`
2. **LlamaRisk Dashboard**
   `GET https://api.llamarisk.com/protocols/ethena/overview/all/?format=json`

### What We Monitor

1. **Collateral Ratio**
   `totalBackingAssetsInUsd + reserveFund / totalUsdeSupply`
   • Warn if ratio < **1.01** (≈ 1 % headroom).

2. **Dual-Source Consistency**
   • Ethena vs LlamaRisk supply — alert if they differ by > 0.1 %.
   • Ethena vs LlamaRisk collateral — alert if they differ by > 1 %.

3. **Data Freshness**
   • Any timestamp older than 24 h from either API triggers a stale-data warning.

4. **Reserve Fund Drift** *(future)*
   • Placeholder for tracking large week-over-week drops.

### Alert Channels

Messages are sent via the shared `utils.telegram.send_telegram_message` helper to the `ETHENA` Telegram channel.
