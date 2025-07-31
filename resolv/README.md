# RESOLV Protocol Monitoring

The script [resolv/resolv.py](resolv.py) runs [hourly via GitHub Actions](../.github/workflows/hourly.yml) to monitor key health indicators of the RESOLV protocol using on-chain data.

## Monitored Contracts

- **USR Price Storage**: `0x7f45180d6fFd0435D8dD695fd01320E6999c261c`
- **USR Redemption**: `0x60A7B7915980ed34fDE6e239618fAdCf67897c37`

The script [resolv/resolv.py](resolv.py) monitors several critical metrics:

1. **USR Price Stability**
   - Alerts if USR price deviates from 1e18 ($1.00)
   - Monitors USR supply and reserves
   - Alerts if USR supply exceeds 130% of reserves

2. **Redemption Usage**
   - Tracks current redemption usage against redemption limit
   - Alerts if usage exceeds 50% of the limit
   - Redemption usage is reset after 24 hours

3. **Price Data Freshness**
   - Monitors timestamp of last price update
   - Alerts if data is older than 24 hours

## Governance

Monitor multisig: [0xD6889F307BE1b83Bb355d5DA7d4478FB0d2Af547](https://etherscan.io/address/0xD6889F307BE1b83Bb355d5DA7d4478FB0d2Af547) that manages all critical functions of the protocol.
