from utils.abi import load_abi
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

ASSET_BONDS_EXCEEDED = "GYR#357"
PROTOCOL = "PEGS"
PEG_THRESHOLD = 80

# Load Balancer Vault ABI
ABI_BALANCER_VAULT = load_abi("common-abi/BalancerVault.json")

BALANCER_VAULT_ADDRESS = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"

# Pool configurations
POOL_CONFIGS = [
    # name, pool id, index of lrt, index of pool token
    (
        "Renzo ezETH-WETH 50-50 Pool",
        "0x596192bb6e41802428ac943d2f1476c1af25cc0e000000000000000000000659",
        1,
        0,
    ),
    (
        "Kelp rsETH-WETH 50-50 Pool",
        "0x58aadfb1afac0ad7fca1148f3cde6aedf5236b6d00000000000000000000067f",
        1,
        0,
    ),
    (
        "Puffer pufETH-wstETH 50-50 Pool",
        "0x63e0d47a6964ad1565345da9bfa66659f4983f02000000000000000000000681",
        2,
        0,
    ),
    (
        "Ether.fi weETH-rETH 50-50 Pool",
        "0x05ff47afada98a98982113758878f9a8b9fdda0a000000000000000000000645",
        2,
        0,
    ),
    (
        "Stader ETHx-wstETH 50-50 Pool",
        "0xb91159aa527d4769cb9faf3e4adb760c7e8c8ea700000000000000000000067c",
        1,
        2,
    ),
    (
        "apxETH-WETH 50-50 Pool",
        "0x88794c65550deb6b4087b7552ecf295113794410000000000000000000000648",
        0,
        1,
    ),
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
        print(f"{pool_name} ratio is {percentage:.2f}%")
        if percentage > PEG_THRESHOLD:
            message = f"🚨 Balancer Alert! {pool_name} ratio is {percentage:.2f}% 🚀 "
            send_telegram_message(message, PROTOCOL, True)


def main():
    print("Checking Balancer pools...")
    process_pools()


if __name__ == "__main__":
    main()
