from utils.abi import load_abi
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "comp"
THRESHOLD_UR = 0.99
THRESHOLD_UR_NOTIFICATION = 0.99

ABI_CTOKEN = load_abi("compound/abi/CTokenV3.json")

# Map addresses by chain
ADDRESSES_BY_CHAIN = {
    Chain.MAINNET: [
        "0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840",
        "cUSDTv3",
        "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        "cUSDCv3",
        "0xA17581A9E3356d9A858b789D68B4d866e593aE94",
        "cWETHv3",
    ],
}


def print_stuff(chain_name, token_name, ur):
    if ur > THRESHOLD_UR:
        message = (
            f"🚨 **BEEP BOP** 🚨\n💎 Market asset: {token_name}\n📊 Utilization rate: {ur:.2%}\n🌐 Chain: {chain_name}"
        )
        disable_notification = True if ur <= THRESHOLD_UR_NOTIFICATION else False
        send_telegram_message(message, PROTOCOL, disable_notification)


def process_assets(chain: Chain):
    client = ChainManager.get_client(chain)
    addresses = ADDRESSES_BY_CHAIN[chain]

    with client.batch_requests() as batch:
        contracts = []
        for i in range(0, len(addresses), 2):
            ctoken_address = addresses[i]
            ctoken = client.eth.contract(address=ctoken_address, abi=ABI_CTOKEN)
            contracts.append(ctoken)
            batch.add(ctoken.functions.getUtilization())

        responses = client.execute_batch(batch)
        expected_responses = len(addresses) // 2
        if len(responses) != expected_responses:
            raise ValueError(f"Expected {expected_responses} responses from batch, got: {len(responses)}")

    for i, response in enumerate(responses):
        ur = int(response) / 1e18
        ctoken_name = addresses[i * 2 + 1]
        print_stuff(chain.name, ctoken_name, ur)


def main():
    for chain in [Chain.MAINNET]:
        print(f"Processing {chain.name} assets...")
        process_assets(chain)


if __name__ == "__main__":
    main()
