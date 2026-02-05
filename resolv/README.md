# RESOLV Protocol Monitoring

The script [resolv/resolv.py](resolv.py) runs [hourly via GitHub Actions](../.github/workflows/hourly.yml) to monitor key health indicators of the RESOLV protocol using on-chain data.

## Monitored Contracts

- **USR Price Storage**: `0x7f45180d6fFd0435D8dD695fd01320E6999c261c`
- **USR Redemption**: `0x60A7B7915980ed34fDE6e239618fAdCf67897c37`

The script [resolv/resolv.py](resolv.py) monitors several critical metrics:

1. **USR Price Stability**
   - Alerts if USR price deviates from 1e18 ($1.00)
   - Monitors USR supply and reserves
   - Alerts if over-collateralization is below 130% (i.e., if reserves are less than 130% of USR supply)
   - Alerts if USR supply is zero or invalid

2. **Redemption Usage**
   - Tracks current redemption usage against redemption limit
   - Alerts if usage exceeds 50% of the limit
   - Uses smart caching to prevent spam alerts:
     - Alerts on first run if above threshold
     - Alerts when 24h reset is detected and usage is above threshold
     - Alerts when threshold is crossed (goes from below to above 50%)
     - Alerts once per 24h period if usage remains above threshold

3. **Price Data Freshness**
   - Monitors timestamp of last price update
   - Alerts if data is older than 24 hours

4. **Off-chain Reserves Dashboard**
   - Pulls metrics from `https://info.apostro.xyz/resolv-reserves`
   - Alerts if fetch fails or parsing fails
   - Alerts if required fields are missing
   - Alerts if reserves data timestamp is missing or unparseable
   - Alerts if reserves data is older than 6 hours
   - Alerts if USR over-collateralization is below 130%
   - Alerts if market delta absolute value exceeds 3%
   - Alerts if strategy net exposure exceeds 3% of TVL
   - Alerts on percentage changes:
     - TVL change ≥ 10%
     - USR TVL change ≥ 10%
     - RLP TVL change ≥ 10%
     - Backing assets value change ≥ 5%
   - Alerts if RLP/USR ratio changes by ≥ 5% (absolute)

## Governance

Monitor multisig: [0xD6889F307BE1b83Bb355d5DA7d4478FB0d2Af547](https://etherscan.io/address/0xD6889F307BE1b83Bb355d5DA7d4478FB0d2Af547) that manages all critical functions of the protocol.
