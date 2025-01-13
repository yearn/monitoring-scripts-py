# USD0 - Usual Money

**Monitoring - DISABLED**

[Usual](https://usual.money/) is team behind stablecoin USD0. For more info check [this post by Llama Risk](https://www.llamarisk.com/research/pegkeeper-onboarding-usd0).

## Governance

Protocol governance is managed through a [8/15 multisig without timelock](https://etherscan.io/address/0x6e9d65eC80D69b1f508560Bc7aeA5003db1f7FB7). The team intends to add timelocks to their multisigs when the associated functions and roles are significant. All smart contracts are verified onchain and upgradeable through protocol governance mechanisms.

We are monitoring [multisig address](safe/main.py#162) for new queued transactions.

TODO: think about monitoring pause role multisigs, like newly added [proxy](https://etherscan.io/address/0x30f1A5916b93ac55AE222EbA9d5a7B0aBb0Ab49A). Here is the [list of roles](https://vscode.blockscan.com/ethereum/0x73A15FeD60Bf67631dC6cd7Bc5B6e8da8190aCF5).

## Collateral Factor

Usual maintains an insurance fund mechanism as part of its protocol treasury rather than utilizing a separate vault structure. The fund serves as a protective buffer against extreme market events and temporary collateral value fluctuations. The Protocol aims to maintain a minimum 30 basis points (bps) protective buffer at all times to ensure collateral security.

Running daily script to check the collateral factor value.

## USD0 Price Peg

Running hourly script to check the peg of USD0. It uses Curve pool USD0/USDC to check the peg.

## Treasury

TODO: we could monitor treasury contract: https://etherscan.io/address/0xdd82875f0840AAD58a455A70B88eEd9F59ceC7c7
