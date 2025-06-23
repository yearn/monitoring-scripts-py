# Ethena

## Overview

Ethena is a synthetic dollar protocol built on Ethereum that provides a crypto-native solution for money, USDe, alongside a globally accessible dollar savings asset, sUSDe.

## Monitoring

The script [`ethena/ethena.py`](ethena.py) runs **hourly via GitHub Actions** to sanity-check that **USDe remains fully backed** and that the public data feeds are fresh and internally consistent. Telegram messages are sent if some values are out of the expected range.

### Data Sources

Data used is provided by Ethena on [transparency page](https://app.ethena.fi/dashboards/transparency) and LlamaRisk:

1. **Ethena Transparency**
   • Collateral: `GET /positions/current/collateral?latest=true`
   • Supply  : `GET /solvency/token-supply?symbol=USDe`
2. **LlamaRisk Dashboard**
   `GET https://api.llamarisk.com/protocols/ethena/overview/all/?format=json`

> NOTE: Ethena data is not available when running on Github Actions, so we use LlamaRisk data only.

### What We Monitor

1. **Collateral Ratio**
   `totalBackingAssetsInUsd + reserveFund / totalUsdeSupply`
   • Warn if ratio < **1.01**

2. **Dual-Source Consistency**
   • Ethena vs LlamaRisk supply — alert if they differ by > 0.1%
   • Ethena vs LlamaRisk collateral — alert if they differ by > 0.1%

3. **Data Freshness**
   • If collateral or chain data is older than 6h from either API triggers a stale-data warning. Also, if reserve data is older than 12 h, send a warning.
