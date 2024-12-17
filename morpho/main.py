from web3 import Web3
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message
from utils.cache import (
    get_last_executed_morpho_from_file,
    write_last_executed_morpho_to_file,
)

# Load environment variables
load_dotenv()

PROTOCOL = "MORPHO"
MARKET_URL = "https://app.morpho.org/market"
VAULT_URL = "https://app.morpho.org/vault"
# Provider URLs
PROVIDER_URL_MAINNET = os.getenv("PROVIDER_URL_MAINNET")
PROVIDER_URL_BASE = os.getenv("PROVIDER_URL_BASE")

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


def get_market_url(market_hex, chain):
    market = Web3.to_hex(market_hex)
    return f"{MARKET_URL}?id={market}&network={chain}"


def get_vault_url_by_name(vault_name, chain):
    vaults = MAINNET_VAULTS if chain == "mainnet" else BASE_VAULTS
    for name, address in vaults:
        if name == vault_name:
            return f"{VAULT_URL}?vault={address}&network={chain}"
    return None


def check_markets_pending_cap(name, morpho_contract, chain, w3):
    with w3.batch_requests() as batch:
        batch.add(morpho_contract.functions.supplyQueueLength())
        batch.add(morpho_contract.functions.withdrawQueueLength())

        length_responses = batch.execute()
        if len(length_responses) != 2:
            raise ValueError(
                "Expected 2 responses from batch, got: ", len(length_responses)
            )
        length_of_supply_queue = length_responses[0]
        length_of_withdraw_queue = length_responses[1]

    vault_address = morpho_contract.address
    with w3.batch_requests() as batch:
        for i in range(length_of_supply_queue):
            batch.add(morpho_contract.functions.supplyQueue(i))
        for i in range(length_of_withdraw_queue):
            batch.add(morpho_contract.functions.withdrawQueue(i))
        market_responses = batch.execute()
        if len(market_responses) != length_of_supply_queue + length_of_withdraw_queue:
            raise ValueError(
                "Expected 2 responses from batch, got: ", len(market_responses)
            )

    with w3.batch_requests() as batch:
        for i in range(0, length_of_supply_queue):
            batch.add(morpho_contract.functions.pendingCap(market_responses[i]))
        for i in range(
            length_of_supply_queue, length_of_supply_queue + length_of_withdraw_queue
        ):
            batch.add(morpho_contract.functions.pendingCap(market_responses[i]))
        pending_cap_responses = batch.execute()

    market_type = "supply"
    for i in range(0, length_of_supply_queue):
        supply_market = market_responses[i]
        pending_cap_timestamp = pending_cap_responses[i][1]  # [1] to get the timestamp
        if pending_cap_timestamp > 0:
            if pending_cap_timestamp > get_last_executed_morpho_from_file(
                vault_address, market_type
            ):
                market_url = get_market_url(supply_market, chain)
                vault_url = get_vault_url_by_name(name, chain)
                send_telegram_message(
                    f"Updating supply cap to higher value for vault {name}({vault_url}) for market: {market_url}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market_type, pending_cap_timestamp
                )

    market_type = "withdraw"
    for i in range(
        length_of_supply_queue, length_of_supply_queue + length_of_withdraw_queue
    ):
        withdraw_market = market_responses[i]
        pending_cap_timestamp = pending_cap_responses[i][1]  # [1] to get the timestamp
        if pending_cap_timestamp > 0:
            if pending_cap_timestamp > get_last_executed_morpho_from_file(
                vault_address, market_type
            ):
                market_url = get_market_url(withdraw_market, chain)
                vault_url = get_vault_url_by_name(name, chain)
                send_telegram_message(
                    f"Updating withdraw cap to higher value for vault {name}({vault_url}) for market: {market_url}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market_type, pending_cap_timestamp
                )


def check_pending_role_change(name, morpho_contract, role_type, timestamp):
    if timestamp > get_last_executed_morpho_from_file(
        morpho_contract.address, role_type
    ):
        send_telegram_message(
            f"{role_type.capitalize()} is changing for vault {name}", PROTOCOL
        )
        write_last_executed_morpho_to_file(
            morpho_contract.address, role_type, timestamp
        )


def check_timelock_and_guardian(name, morpho_contract):
    with morpho_contract.w3.batch_requests() as batch:
        batch.add(morpho_contract.functions.pendingTimelock())
        batch.add(morpho_contract.functions.pendingGuardian())
        responses = batch.execute()
        if len(responses) != 2:
            raise ValueError("Expected 2 responses from batch, got: ", len(responses))

        timelock = responses[0][1]  # [1] to get the timestamp
        guardian = responses[1][1]  # [1] to get the timestamp

    check_pending_role_change(name, morpho_contract, "timelock", timelock)
    check_pending_role_change(name, morpho_contract, "guardian", guardian)


def get_data_for_chain(chain):
    if chain == "mainnet":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_MAINNET))
        vaults = MAINNET_VAULTS
    elif chain == "base":
        w3 = Web3(Web3.HTTPProvider(PROVIDER_URL_BASE))
        vaults = BASE_VAULTS
    else:
        raise ValueError("Invalid chain")

    print(f"Processing Morpho Vaults on {chain} ...")
    print(f"Vaults: {vaults}")

    for vault in vaults:
        # TODO: additional optimization is possible by combining marketes of all vaults into one list
        # and then checking the pending caps for all markets in one batch request
        morpho_contract = w3.eth.contract(address=vault[1], abi=ABI_MORPHO)
        check_markets_pending_cap(vault[0], morpho_contract, chain, w3)
        check_timelock_and_guardian(vault[0], morpho_contract)


def main():
    get_data_for_chain("mainnet")
    # get_data_for_chain("base")


if __name__ == "__main__":
    main()
