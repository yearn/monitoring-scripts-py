import json

from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "comp"
THRESHOLD_UR = 0.99
THRESHOLD_UR_NOTIFICATION = 0.99


def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


ABI_CTOKEN = load_abi("compound/abi/CTokenV3.json")

# Map addresses by chain
ADDRESSES_BY_CHAIN = {
    Chain.POLYGON: [
        "0xF25212E676D1F7F89Cd72fFEe66158f541246445",
        "cUSDC.Ev3",
        "0xaeB318360f27748Acb200CE616E389A6C9409a07",
        "cUSDTv3",
    ],
    Chain.MAINNET: [
        "0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840",
        "cUSDTv3",
        "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        "cUSDCv3",
        "0xA17581A9E3356d9A858b789D68B4d866e593aE94",
        "cWETHv3",
    ],
    Chain.ARBITRUM: [
        "0xd98Be00b5D27fc98112BdE293e487f8D4cA57d07",
        "cUSDTv3",
        "0x6f7D514bbD4aFf3BcD1140B7344b32f063dEe486",
        "cWETHv3",
        "0xA5EDBDD9646f8dFF606d7448e414884C7d905dCA",
        "cUSDC.Ev3",
        "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf",
        "cUSDCv3",
    ],
    # We don't use optimism - add if needed
    # Chain.OPTIMISM: [
    #     "0x2e44e174f7D53F0212823acC11C01A11d58c5bCB", "cUSDCv3",
    #     "0x995E394b8B2437aC8Ce61Ee0bC610D617962B214", "cUSDTv3",
    #     "0xE36A30D249f7761327fd973001A32010b521b6Fd", "cWETHv3",
    # ]
}


def print_stuff(chain_name, token_name, ur):
    if ur > THRESHOLD_UR:
        message = (
            "🚨 **BEEP BOP** 🚨\n"
            f"💎 Market asset: {token_name}\n"
            f"📊 Utilization rate: {ur:.2%}\n"
            f"🌐 Chain: {chain_name}"
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
            raise ValueError(
                f"Expected {expected_responses} responses from batch, got: {len(responses)}"
            )

    for i, response in enumerate(responses):
        ur = int(response) / 1e18
        ctoken_name = addresses[i * 2 + 1]
        print_stuff(chain.name, ctoken_name, ur)


def main():
    for chain in [Chain.POLYGON, Chain.MAINNET, Chain.ARBITRUM]:
        print(f"Processing {chain.name} assets...")
        process_assets(chain)


if __name__ == "__main__":
    main()
