# LRT Pegs

## Exchange rates

Checks the main liquidity pools of LRTs to detect depegging, such as the ezETH-WETH, rsETH-WETH, pufETH-wstETH, weETH-rETH, ETHx-wstETH and pxETH-WETH pools in Balancer. The bot monitors pool balances and sends a message if they become skewed.

### Lombard Finance (LBTC)

Monitor Lombard LBTC feed by [Redstone](https://docs.redstone.finance/docs/data/lombard/): "Currently, the value has an upper cap of 1, meaning a healthy value is 1, indicating the protocol’s stability.". If the value of LBTC changes in [contract oracle](https://etherscan.io/address/0xb415eAA355D8440ac7eCB602D3fb67ccC1f0bc81) between 2 blocks, we will get notified by [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/eca272ef-979a-47b3-a7f0-2e67172889bb).

### Origin Protocol (superOETH)

Check redeem value of [wsuperOETH](https://basescan.org/address/0xDBFeFD2e8460a6Ee4955A68582F85708BAEA60A3#code) on Base chain and [OETH](https://etherscan.io/address/0x856c4Efb76C1D1AE02e20CEB03A2A6a08b0b8dC3#code) on Mainnet. The redeem value should 1e18, 1-to-1 with ETH. If the redeem value is different, the bot will send a message to Telegram. Additionaly, if the redeem value drops for wrapped OETH, the bot will send a message to Telegram. This check is run on hourly basis.

## Governance

### Ether.fi (eETH)

[eETH](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2) contract is upgradable proxy. Owner of the contract [Timelock](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2#readProxyContract#F10), address: 0x9f26d4c958fd811a1f59b01b86be7dffc9d20761. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/9be6d06d-83a1-46be-bb1a-4bbaa813ef52) is set to notify when a new transaction is created, event CallScheduled emitted.

### Kelp DAO (rsETH)

[rsETH](https://etherscan.io/address/0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7#code) contract is upgradable proxy. Owner of the contrat [Timelock](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1), address: 0x49bd9989e31ad35b0a62c20be86335196a3135b1 with min delay set to [10 days](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1#readContract#F6). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/c8108fff-b1f4-4cb0-abd3-c37ad541e6aa) is set to notify when a new transaction is created, event CallScheduled emitted.

### Renzo (ezETH)

[ezETH](https://etherscan.io/address/0xbf5495Efe5DB9ce00f80364C8B423567e58d2110#code) contract is upgradable proxy. The default admin role is set to the [Timelock](https://etherscan.io/address/0x4994EFc62101A9e3F885d872514c2dC7b3235849#readProxyContract#F17), address: 0x81f6e9914136da1a1d3b1efd14f7e0761c3d4cc7. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/65153e56-1f79-45a2-8453-b61beeeab411) is set to notify when a new transaction is created, event CallScheduled emitted.

### Puffer Finance (pufETH)

[pufETH](https://etherscan.io/address/0xD9A442856C234a39a81a089C06451EBAa4306a72#readProxyContract) contract is upgradable proxy. Contract [authority](https://etherscan.io/address/0xD9A442856C234a39a81a089C06451EBAa4306a72#readProxyContract#F7) is [AccessManager](https://etherscan.io/address/0x8c1686069474410E6243425f4a10177a94EBEE11#code) which admin is set to [Timelock contract](https://etherscan.io/address/0x3C28B7c7Ba1A1f55c9Ce66b263B33B204f2126eA). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/f6654146-08d0-4a83-917a-23233be2314e) is set to notify when a new transaction is queued by calling [`queueTransaction()`](https://etherscan.io/address/0x3C28B7c7Ba1A1f55c9Ce66b263B33B204f2126eA#writeContract#F5).

### Lombard Finance (LBTC)

Monitoring [multisig of LBTC boring vault](https://etherscan.io/address/0xb7cB7131FFc18f87eEc66991BECD18f2FF70d2af) that can change all settings of Veda vault. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/271040e6-85bc-4103-bf05-094a9912961a) is set to notify when a new transaction is scheduled, event CallScheduled emitted, in Lombard Timelock. This contract is the owner of [LBTC token](https://etherscan.io/token/0x8236a87084f8B84306f72007F36F2618A5634494#readProxyContract#F18).

### Dinero protocol (apxETH)

[apxETH](https://etherscan.io/address/0xD664b74274DfEB538d9baC494F3a4760828B02b0) contract ERC4626 wrapper for pxETH that autocompounds rewards. The admin of the contract is Redacted cartel [multisig 3/7](https://app.safe.global/transactions/history?safe=eth%3A0xA52Fd396891E7A74b641a2Cb1A6999Fcf56B077e), address: 0xA52Fd396891E7A74b641a2Cb1A6999Fcf56B077e. This multisig if monitored with [Safe script](../safe/main.py#L200).

### Origin Protocol (superOETH)

[superOETH](https://basescan.org/address/0xDBFeFD2e8460a6Ee4955A68582F85708BAEA60A3#code) contract is upgradable proxy on Base chain. The default admin role is set to the [Timelock](https://basescan.org/address/0xdbfefd2e8460a6ee4955a68582f85708baea60a3#readProxyContract#F6), address: 0xf817cb3092179083c48c014688d98b72fb61464f with min delay set to [2 days](https://basescan.org/address/0xf817cb3092179083c48c014688d98b72fb61464f#readContract#F6). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/12da72da-b69c-40c6-862a-9d88538be13c) is set to notify when a new transaction is created, event CallScheduled emitted.
>>>>>>> main
