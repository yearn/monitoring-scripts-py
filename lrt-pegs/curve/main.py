from utils.abi import load_abi
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "PEGS"
PEG_THRESHOLD = 80

# Load Balancer Vault ABI
ABI_CURVE_POOL = load_abi("lrt-pegs/abi/CurvePool.json")

# Pool configurations
POOL_CONFIGS = [
    # name, pool address, index of lrt, index of other asset
    (
        "pufETH-wstETH Curve Pool",
        "0xEEda34A377dD0ca676b9511EE1324974fA8d980D",
        0,
        1,
    ),
    (
        "weETH-WETH Curve Pool",
        "0xDB74dfDD3BB46bE8Ce6C33dC9D82777BCFc3dEd5",
        1,
        0,
    ),
]


def process_pools(chain: Chain = Chain.MAINNET):
    client = ChainManager.get_client(chain)
    contracts = []

    # Prepare batch calls
    with client.batch_requests() as batch:
        for _, pool_address, _, _ in POOL_CONFIGS:
            pool = client.eth.contract(address=pool_address, abi=ABI_CURVE_POOL)
            contracts.append(pool)

            batch.add(pool.functions.get_balances())

        responses = client.execute_batch(batch)
        if len(responses) != len(POOL_CONFIGS):
            raise ValueError(f"Expected {len(POOL_CONFIGS)} responses from batch, got: {len(responses)}")

    # Process results
    for (pool_name, _, idx_lrt, idx_other_token), balances in zip(POOL_CONFIGS, responses):
        percentage = (balances[idx_lrt] / (balances[idx_lrt] + balances[idx_other_token])) * 100
        print(f"{pool_name} ratio is {percentage:.2f}%")
        if percentage > PEG_THRESHOLD:
            message = f"🚨 Curve Alert! {pool_name} ratio is {percentage:.2f}% 🚀 "
            send_telegram_message(message, PROTOCOL, True)


def main():
    print("Checking Curve pools...")
    process_pools()


if __name__ == "__main__":
    main()
