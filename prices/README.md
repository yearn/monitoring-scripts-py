# Depeg Monitoring

Centralized depeg monitoring for LRTs and stablecoins. Runs two types of checks:

1. **Fundamental oracle check** — reads Redstone on-chain push oracles. Any depeg (below 0.998) triggers a CRITICAL alert.
2. **DefiLlama market price check** — fetches USD prices and computes ratios vs underlying (ETH or USD). A 2%+ depeg (below 0.98) triggers a CRITICAL alert.

All LRT alerts are routed to the `lrt` Telegram channel. Stablecoin alerts go to `stables`.

## Fundamental Oracles

### LBTC (Lombard Bitcoin)
- **Oracle**: Redstone LBTC_FUNDAMENTAL push oracle
- **Address**: `0xb415eAA355D8440ac7eCB602D3fb67ccC1f0bc81` (Ethereum Mainnet)
- **Interface**: AggregatorV3 (`latestRoundData()`, 8 decimals)
- **Update**: 24h heartbeat / 1% deviation
- **Tenderly alert**: `eca272ef-979a-47b3-a7f0-2e67172889bb` — monitors value changes between blocks

### cUSD (CAP Protocol)
- **Oracle**: Redstone cUSD_FUNDAMENTAL push oracle
- **Address**: `0x9a5a3c3ed0361505cc1d4e824b3854de5724434a` (Ethereum Mainnet)
- **Interface**: AggregatorV3 (`latestRoundData()`, 8 decimals)
- **Tenderly alert**: `316f440e-457b-4cfa-a69e-f7f54230bf44` — alerts when `latestAnswer()` drops below 99980000 (0.9998)

## DefiLlama-Monitored Assets

These assets do not have on-chain fundamental push oracles on Ethereum mainnet. Redstone provides off-chain fundamental feeds (pull model) for weETH, ezETH, rsETH, pufETH but they require calldata injection at transaction time and cannot be read directly on-chain.

### LRTs (vs ETH)
| Token  | Address | Redstone fundamental (off-chain) |
|--------|---------|----------------------------------|
| weETH  | `0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee` | weETH_FUNDAMENTAL (~1.09) |
| ezETH  | `0xbf5495Efe5DB9ce00f80364C8B423567e58d2110` | ezETH_FUNDAMENTAL (~1.08) |
| rsETH  | `0xA1290d69c65A6Fe4DF752f95823Fae25cB99e5A7` | rsETH_FUNDAMENTAL (~1.07) |
| pufETH | `0xD9A442856C234a39a81a089C06451EBAa4306a72` | pufETH_FUNDAMENTAL (~1.07) |
| osETH  | `0xf1C9acDc66974dFB6dEcB12aA385b9cD01190E38` | — |
| rswETH | `0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0` | — |
| mETH   | `0xd5F7838F5C461fefF7FE49ea5ebaF7728bB0ADfa` | — |

### Stablecoins (vs USD)
| Token  | Address |
|--------|---------|
| FDUSD  | `0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409` |
| deUSD  | `0x15700B564Ca08D9439C58cA5053166E8317aa138` |
| USD0   | `0x73A15FeD60Bf67631dC6cd7Bc5B6e8da8190aCF5` |
| USD0++ | `0x35D8949372D46B7a3D5A56006AE77B215fc69bC0` |
| USDe   | `0x4c9EDD5852cd905f086C759E8383e09bff1E68B3` |

## Tenderly Alert Coverage

| Asset | Tenderly Alert | Status |
|-------|---------------|--------|
| LBTC  | `eca272ef-...` (value change between blocks) | Covered |
| cUSD  | `316f440e-...` (latestAnswer < 0.9998) | Covered |
| weETH | — | **Needs Tenderly alert** if on-chain push oracle deployed |
| ezETH | — | **Needs Tenderly alert** if on-chain push oracle deployed |
| rsETH | — | **Needs Tenderly alert** if on-chain push oracle deployed |
| pufETH | — | **Needs Tenderly alert** if on-chain push oracle deployed |
| Others | N/A (DefiLlama only) | Monitored by this script |

## Creating Tenderly Alerts for New Oracles

If Redstone deploys on-chain push oracles for weETH, ezETH, rsETH, or pufETH on Ethereum mainnet, create Tenderly alerts with:
- **Network**: Ethereum Mainnet
- **Contract address**: The oracle contract
- **Alert type**: Transaction — function call `latestAnswer()` returns value below threshold
- **Threshold**: 99800000 (0.998 with 8 decimals) for LRTs, 99980000 (0.9998) for stables
- **Delivery**: Telegram channel for the respective protocol
