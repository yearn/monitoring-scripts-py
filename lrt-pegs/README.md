# LRT Pegs

## Exchange rates

Checks the main liquidity pools of LRTs to detect depegging, such as the ezETH-WETH and rsETH-WETH pools in Balancer. The bot monitors pool balances and sends a message if they become skewed.

## Governance

### Ether.fi

[eETH](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2) contract is upgradable proxy. Owner of the contrat [Timelock](https://etherscan.io/address/0x35fA164735182de50811E8e2E824cFb9B6118ac2#readProxyContract#F10), address: 0x9f26d4c958fd811a1f59b01b86be7dffc9d20761. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/9be6d06d-83a1-46be-bb1a-4bbaa813ef52) is set to notify when new transaction created, event CallScheduled emitted.

### Kelp DAO

[rsETH](https://etherscan.io/address/0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7#code) contract is upgradable proxy. Owner of the contrat [Timelock](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1), address: 0x49bd9989e31ad35b0a62c20be86335196a3135b1 with min delay set to [10 days](https://etherscan.io/address/0x49bd9989e31ad35b0a62c20be86335196a3135b1#readContract#F6). [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/c8108fff-b1f4-4cb0-abd3-c37ad541e6aa) is set to notify when new transaction created, event CallScheduled emitted.

### Renzo

[ezETH](https://etherscan.io/address/0xbf5495Efe5DB9ce00f80364C8B423567e58d2110#code) contract is upgradable proxy. Default admin role is set to the [Timelock](https://etherscan.io/address/0x4994EFc62101A9e3F885d872514c2dC7b3235849#readProxyContract#F17), address: 0x81f6e9914136da1a1d3b1efd14f7e0761c3d4cc7. [Tenderly alert](https://dashboard.tenderly.co/yearn/sam/alerts/rules/65153e56-1f79-45a2-8453-b61beeeab411) is set to notify when new transaction created, event CallScheduled emitted.
