import json

from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

ASSET_BONDS_EXCEEDED = "GYR#357"
PROTOCOL = "PEGS"
PEG_THRESHOLD = 80


def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


# Load Balancer Vault ABI
ABI_BALANCER_VAULT = load_abi("common-abi/BalancerVault.json")

BALANCER_VAULT_ADDRESS = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"

# Pool configurations
POOL_CONFIGS = [
    # name, pool id, index of lrt, is BPT token an underlying token?
    (
        "Renzo ezETH-WETH 50-50 Pool",
        "0x596192bb6e41802428ac943d2f1476c1af25cc0e000000000000000000000659",
        1,
        True,
    ),
    (
        "Kelp rsETH-WETH 50-50 Pool",
        "0x58aadfb1afac0ad7fca1148f3cde6aedf5236b6d00000000000000000000067f",
        1,
        True,
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
            raise ValueError(
                f"Expected {len(POOL_CONFIGS)} responses from batch, got: {len(responses)}"
            )

    # Process results
    for (pool_name, _, idx_lrt, is_nested), response in zip(POOL_CONFIGS, responses):
        _, balances, _ = response

        total = 0
        start_index = 1 if is_nested else 0
        for i in range(start_index, len(balances)):
            total += balances[i]

        percentage = (balances[idx_lrt] / total) * 100
        if percentage > PEG_THRESHOLD:
            message = f"🚨 Balancer Alert! {pool_name} ratio is {percentage:.2f}% 🚀 "
            send_telegram_message(message, PROTOCOL, True)


def main():
    print("Checking Balancer pools...")
    process_pools()


if __name__ == "__main__":
    main()
