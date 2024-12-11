from web3 import Web3
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message
from utils.cache import (
    get_last_executed_morpho_from_file,
    write_last_executed_morpho_to_file,
)

# TODO: need to bundle blockchain calls because we get reverts for too many calls

# Load environment variables
load_dotenv()

PROTOCOL = "TEST"  # TODO: add env values for telegram for protocol MORPHO
# Provider URLs
PROVIDER_URL_MAINNET = os.getenv("PROVIDER_URL_MAINNET")
PROVIDER_URL_BASE = os.getenv(
    "PROVIDER_URL_BASE"
)  # TODO: add base provider URL to gh actions

# format of the vault list item is: [name, address]
MAINNET_VAULTS = [
    ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"],
    ["Usual Boosted USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D"],
    ["Gantlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618"],
    ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d"],
    ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658"],
    ["Gantlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458"],
    ["Gantlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5"],
]
BASE_VAULTS = [
    ["Moonwell Flagship USDC", "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca"],
]


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
    vault_address = morpho_contract.address
    length_of_supply_queue = morpho_contract.functions.supplyQueueLength().call()
    market_type = "supply"
    for i in range(length_of_supply_queue):
        supply_markets = morpho_contract.functions.supplyQueue(i).call()
        pending_cap_timestamp = morpho_contract.functions.pendingCap(
            supply_markets
        ).call()[1]
        if pending_cap_timestamp > 0:
            if pending_cap_timestamp > get_last_executed_morpho_from_file(
                vault_address, market_type
            ):
                send_telegram_message(
                    f"Updating supply cap for market: {supply_markets} to higher value for vault {name}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market_type, pending_cap_timestamp
                )

    length_of_withdraw_queue = morpho_contract.functions.withdrawQueueLength().call()
    market_type = "withdraw"
    for i in range(length_of_withdraw_queue):
        withdraw_market = morpho_contract.functions.withdrawQueue(i).call()
        pending_cap_timestamp = morpho_contract.functions.pendingCap(
            withdraw_market
        ).call()[1]
        if pending_cap_timestamp > 0:
            if pending_cap_timestamp > get_last_executed_morpho_from_file(
                vault_address, market_type
            ):
                send_telegram_message(
                    f"Updating withdraw cap for market: {withdraw_market} to higher value for vault {name}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market_type, pending_cap_timestamp
                )
    # TODO: combine multiple messages into one


def check_timelock(name, morpho_contract):
    value_type = "timelock"
    timelock = morpho_contract.functions.pendingTimelock().call()[1]
    if timelock > get_last_executed_morpho_from_file(
        morpho_contract.address, value_type
    ):
        send_telegram_message(f"Timelock is changing for vault {name}", PROTOCOL)
        write_last_executed_morpho_to_file(
            morpho_contract.address, value_type, timelock
        )


def check_guardian(name, morpho_contract):
    value_type = "guardian"
    guardian = morpho_contract.functions.pendingGuardian().call()[1]
    if guardian > get_last_executed_morpho_from_file(
        morpho_contract.address, value_type
    ):
        send_telegram_message(f"Guardian is changing for vault {name}", PROTOCOL)
        write_last_executed_morpho_to_file(
            morpho_contract.address, value_type, guardian
        )


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
        morpho_contract = w3.eth.contract(address=vault[1], abi=ABI_MORPHO)
        check_markets_pending_cap(vault[0], morpho_contract)
        check_timelock(vault[0], morpho_contract)
        check_guardian(vault[0], morpho_contract)


def main():
    get_data_for_chain("mainnet")
    # get_data_for_chain("base")


if __name__ == "__main__":
    main()
