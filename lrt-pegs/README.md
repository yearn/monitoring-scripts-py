# LRT Pegs

## Exchange rates

Checks the main liquidity pools of LRTs to detect depegging, such as the ezETH-WETH, rsETH-WETH, pufETH-wstETH, weETH-rETH and ETHx-wstETH pools in Balancer. The bot monitors pool balances and sends a message if they become skewed.

## Governance

### Ether.fi (eETH)

[eETH](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2) contract is upgradable proxy. Owner of the contrat [Timelock](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2#readProxyContract#F10), address: 0x9f26d4c958fd811a1f59b01b86be7dffc9d20761. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/9be6d06d-83a1-46be-bb1a-4bbaa813ef52) is set to notify when new transaction created, event CallScheduled emitted.

### Kelp DAO (rsETH)

[rsETH](https://etherscan.io/address/0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7#code) contract is upgradable proxy. Owner of the contrat [Timelock](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1), address: 0x49bd9989e31ad35b0a62c20be86335196a3135b1 with min delay set to [10 days](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1#readContract#F6). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/c8108fff-b1f4-4cb0-abd3-c37ad541e6aa) is set to notify when new transaction created, event CallScheduled emitted.

### Renzo (ezETH)

[ezETH](https://etherscan.io/address/0xbf5495Efe5DB9ce00f80364C8B423567e58d2110#code) contract is upgradable proxy. Default admin role is set to the [Timelock](https://etherscan.io/address/0x4994EFc62101A9e3F885d872514c2dC7b3235849#readProxyContract#F17), address: 0x81f6e9914136da1a1d3b1efd14f7e0761c3d4cc7. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/65153e56-1f79-45a2-8453-b61beeeab411) is set to notify when new transaction created, event CallScheduled emitted.

### Puffer Finance (pufETH)

[pufETH](https://etherscan.io/address/0xD9A442856C234a39a81a089C06451EBAa4306a72#readProxyContract) contract is upgradable proxy. Contract [authority](https://etherscan.io/address/0xD9A442856C234a39a81a089C06451EBAa4306a72#readProxyContract#F7) is [AccessManager](https://etherscan.io/address/0x8c1686069474410E6243425f4a10177a94EBEE11#code) which admin is set to [Timelock contract](https://etherscan.io/address/0x3C28B7c7Ba1A1f55c9Ce66b263B33B204f2126eA). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/f6654146-08d0-4a83-917a-23233be2314e) is set to notify when a new transaction is queued by calling [`queueTransaction()`](https://etherscan.io/address/0x3C28B7c7Ba1A1f55c9Ce66b263B33B204f2126eA#writeContract#F5).

### Lombard Finance (LBTC)

Monitor Lombard LBTC feed by [Redstone](https://docs.redstone.finance/docs/data/lombard/): "Currently, the value has an upper cap of 1, meaning a healthy value is 1, indicating the protocol’s stability.". If the value of LBTC changes in [contract oracle](https://etherscan.io/address/0xb415eAA355D8440ac7eCB602D3fb67ccC1f0bc81) between 2 blocks, we will get notified by [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/eca272ef-979a-47b3-a7f0-2e67172889bb).
