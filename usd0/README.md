# USD0 - Usual Money

[Usual](https://usual.money/) is team behind stablecoin USD0. For more info check [this post by Llama Risk](https://www.llamarisk.com/research/pegkeeper-onboarding-usd0).

## Governance

Protocol governance is managed through a [5/9 multisig without timelock](https://etherscan.io/address/0x6e9d65eC80D69b1f508560Bc7aeA5003db1f7FB7). The team intends to add timelocks to their multisigs when the associated functions and roles are significant. All smart contracts are verified onchain and upgradeable through protocol governance mechanisms.

We are monitoring [ms address](safe/main.py#162).

## Collateral Factor

Usual maintains an insurance fund mechanism as part of its protocol treasury rather than utilizing a separate vault structure. The fund serves as a protective buffer against extreme market events and temporary collateral value fluctuations. The Protocol aims to maintain a minimum 30 basis points (bps) protective buffer at all times to ensure collateral security.

Running daily script to check the collateral factor value.

## USD0 Price Peg

Running hourly script to check the peg of USD0. It uses Curve pool USD0/USDC to check the peg.
