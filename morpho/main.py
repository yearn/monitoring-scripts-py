from web3 import Web3
from dotenv import load_dotenv
import os, json, datetime
from utils.telegram import send_telegram_message

# Load environment variables
load_dotenv()

PROTOCOL = "MORPHO"
# Provider URLs
PROVIDER_URL_MAINNET = os.getenv("PROVIDER_URL_MAINNET")
PROVIDER_URL_BASE = os.getenv("PROVIDER_URL_BASE") # TODO: add base provider URL to gh actions

# format of the vault list item is: [name, chain, address]
MAINNET_VAULTS = [["Steakhouse USDC", "mainnet", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"]]
BASE_VAULTS = []

# Load ABI files
def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


ABI_MORPHO = load_abi("morpho/abi/morpho.json")

def check_markets_pending_cap(name, morpho_contract):
    length_of_supply_queue = morpho_contract.functions.supplyQueueLength().call()
    # iterate through the supply queue and check if the pending cap is higher than the current cap
    for i in range(length_of_supply_queue):
        supply_markets = morpho_contract.functions.supplyQueue(i).call()
        pending_cap = morpho_contract.functions.pendingCap(supply_markets).call()
        if pending_cap[1] > 0:
            # TODO: combine multiple messages into one
            send_telegram_message(f"Updating supply cap to higher value for vault {name}", PROTOCOL)
            # TODO: cache the pending cap to avoid spamming the telegram channel

    length_of_withdraw_queue = morpho_contract.functions.withdrawQueueLength().call()
    for i in range(length_of_withdraw_queue):
        withdraw_market = morpho_contract.functions.withdrawQueue(i).call()
        pending_cap = morpho_contract.functions.pendingCap(withdraw_market).call()
        if pending_cap[1] > 0:
            send_telegram_message(f"Updating withdraw cap to higher value for vault {name}", PROTOCOL)
            # TODO: cache the pending cap to avoid spamming the telegram channel

    # check if it possible to bundle blockchain calls


def check_timelock(name, morpho_contract):
    timelock = morpho_contract.functions.pendingTimelock().call()
    if timelock[1] > 0:
        send_telegram_message(f"Timelock is changing for vault {name}", PROTOCOL)


def check_guardian(name, morpho_contract):
    guardian = morpho_contract.functions.pendingGuardian().call()
    if guardian[1] > 0:
        send_telegram_message(f"Guardian is changing for vault {name}", PROTOCOL)


def get_data_for_chain(chain):
    if chain == "mainnet":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_MAINNET))
        vaults = MAINNET_VAULTS
    elif chain == "base":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_BASE))
        vaults = BASE_VAULTS
    else:
        raise ValueError("Invalid chain")

    print(f"Processing {chain} assets...")
    print(f"Vaults: {vaults}")

    for vault in vaults:
        morpho_contract = w3.eth.contract(address=vault[2], abi=ABI_MORPHO)
        check_markets_pending_cap(vault[0],morpho_contract)
        check_timelock(vault[0], morpho_contract)
        check_guardian(vault[0], morpho_contract)


def main():
    get_data_for_chain("mainnet")
    get_data_for_chain("base")


if __name__ == "__main__":
    main()
