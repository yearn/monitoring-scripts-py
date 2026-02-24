from utils.abi import load_abi
from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "pegs"
logger = get_logger("lrt-pegs.balancer")
PEG_THRESHOLD = 80

# Load Balancer Vault ABI
ABI_BALANCER_VAULT = load_abi("common-abi/BalancerVault.json")

BALANCER_VAULT_ADDRESS = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"

# Pool configurations
POOL_CONFIGS = [
    # name, pool id, index of lrt, index of pool token
    # (
    #     "Stader ETHx-wstETH 50-50 Pool",
    #     "0xb91159aa527d4769cb9faf3e4adb760c7e8c8ea700000000000000000000067c",
    #     1,
    #     2,
    # ),
]


def process_pools(chain: Chain = Chain.MAINNET):
    client = ChainManager.get_client(chain)
    vault = client.eth.contract(address=BALANCER_VAULT_ADDRESS, abi=ABI_BALANCER_VAULT)

    # Prepare batch calls
    with client.batch_requests() as batch:
        for pool_name, pool_id, _, _ in POOL_CONFIGS:
            batch.add(vault.functions.getPoolTokens(pool_id))

        responses = client.execute_batch(batch)
        if len(responses) != len(POOL_CONFIGS):
            raise ValueError(f"Expected {len(POOL_CONFIGS)} responses from batch, got: {len(responses)}")

    # Process results
    for (pool_name, _, idx_lrt, idx_pool_token), response in zip(POOL_CONFIGS, responses):
        _, balances, _ = response

        total = 0
        for i in range(len(balances)):
            if i == idx_pool_token:
                continue
            total += balances[i]

        percentage = (balances[idx_lrt] / total) * 100
        logger.info("%s ratio is %s%%", pool_name, f"{percentage:.2f}")
        if percentage > PEG_THRESHOLD:
            message = f"🚨 Balancer Alert! {pool_name} ratio is {percentage:.2f}%"
            send_telegram_message(message, PROTOCOL, True)


def main():
    logger.info("Checking Balancer pools...")
    process_pools()


if __name__ == "__main__":
    main()
