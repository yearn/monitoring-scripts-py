from web3 import Web3
from dotenv import load_dotenv
import os, json
from datetime import datetime
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

PENDING_CAP_TYPE = "pending_cap"
REMOVABLE_AT_TYPE = "removable_at"

# format of the vault list item is: [name, address]
MAINNET_VAULTS = [
    ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"],
    ["Usual Boosted USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D"],
    ["Gantlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618"],
    ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d"],
    ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658"],
    ["Gantlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458"],
    ["Gantlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5"],
    ["LlamaRisk crvUSD Vault", "0x67315dd969B8Cd3a3520C245837Bf71f54579C75"],
]
BASE_VAULTS = [
    ["Moonwell Flagship USDC", "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca"],
    ["Moonwell Flagship ETH", "0xa0E430870c4604CcfC7B38Ca7845B1FF653D0ff1"],
    ["Moonwell Flagship EURC", "0xf24608E0CCb972b0b0f4A6446a0BBf58c701a026"],
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


def get_market_url(market, chain):
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
                "Expected 2 responses from batch(supplyQueueLength+withdrawQueueLength), got: ",
                len(length_responses),
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
                "Expected ",
                length_of_supply_queue + length_of_withdraw_queue,
                " responses from batch(supplyQueue+withdrawQueue), got: ",
                len(market_responses),
            )

    markets = list(set(market_responses))

    with w3.batch_requests() as batch:
        for market in markets:
            batch.add(morpho_contract.functions.pendingCap(market))
            batch.add(morpho_contract.functions.config(market))
        pending_cap_and_config_responses = batch.execute()
        if len(pending_cap_and_config_responses) != len(markets) * 2:
            raise ValueError(
                "Expected ",
                len(markets) * 2,
                " responses from batch(pedningCap+config), got: ",
                len(pending_cap_and_config_responses),
            )

    for i in range(0, len(markets)):
        market_id = markets[i]
        market = Web3.to_hex(market_id)

        # Multiply by 2 because there were 2 responses per market and get
        pending_value = pending_cap_and_config_responses[i * 2]
        pending_cap_value = pending_value[0]
        pending_cap_timestamp = pending_value[1]

        # get the current config of the market
        config = pending_cap_and_config_responses[i * 2 + 1]  # Use i * 2 + 1 for config
        current_cap = config[0]  # current cap value is at index 0 in config struct

        # generat urls
        market_url = get_market_url(market, chain)
        vault_url = get_vault_url_by_name(name, chain)

        # pending_cap check
        if pending_cap_timestamp > 0:
            current_time = int(datetime.now().timestamp())
            if pending_cap_timestamp <= current_time:
                # skip if the pending cap is already in the past
                continue

            last_executed_morpho = get_last_executed_morpho_from_file(
                vault_address, market, PENDING_CAP_TYPE
            )

            if pending_cap_timestamp > last_executed_morpho:
                difference_in_percentage = (
                    (pending_cap_value - current_cap) / current_cap
                ) * 100
                time = datetime.fromtimestamp(pending_cap_timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                send_telegram_message(
                    f"Updating cap to new cap {pending_cap_value}, current cap {current_cap}, difference: {difference_in_percentage:.2f}%. \nFor vault {name}({vault_url}) for market: {market_url}. Queued for {time}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market, PENDING_CAP_TYPE, pending_cap_timestamp
                )
            else:
                print(
                    f"Skipping pending cap update for vault {name}({vault_url}) for market: {market_url} because it was already executed"
                )

        # removable_at check
        removable_at = config[2]  # removable_at value is at index 2 in config struct
        if removable_at > 0:
            if removable_at > get_last_executed_morpho_from_file(
                vault_address, market, REMOVABLE_AT_TYPE
            ):
                time = datetime.fromtimestamp(removable_at).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                send_telegram_message(
                    f"Vault {name}({vault_url}) queued to remove market: {market_url} at {time}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(
                    vault_address, market, REMOVABLE_AT_TYPE, removable_at
                )
            else:
                print(
                    f"Skipping removable_at update for vault {name}({vault_url}) for market: {market_url} because it was already executed"
                )


def check_pending_role_change(name, morpho_contract, role_type, timestamp, chain):
    market_id = (
        ""  # use empty string for all markets because the value is used per vault
    )
    if timestamp > get_last_executed_morpho_from_file(
        morpho_contract.address, market_id, role_type
    ):
        vault_url = get_vault_url_by_name(name, chain)
        send_telegram_message(
            f"{role_type.capitalize()} is changing for vault {name}({vault_url})",
            PROTOCOL,
        )
        write_last_executed_morpho_to_file(
            morpho_contract.address, market_id, role_type, timestamp
        )


def check_timelock_and_guardian(name, morpho_contract, chain):
    with morpho_contract.w3.batch_requests() as batch:
        batch.add(morpho_contract.functions.pendingTimelock())
        batch.add(morpho_contract.functions.pendingGuardian())
        responses = batch.execute()
        if len(responses) != 2:
            raise ValueError("Expected 2 responses from batch, got: ", len(responses))

        timelock = responses[0][1]  # [1] to get the timestamp
        guardian = responses[1][1]  # [1] to get the timestamp

    check_pending_role_change(name, morpho_contract, "timelock", timelock, chain)
    check_pending_role_change(name, morpho_contract, "guardian", guardian, chain)


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
        check_timelock_and_guardian(vault[0], morpho_contract, chain)


def main():
    get_data_for_chain("mainnet")
    get_data_for_chain("base")


if __name__ == "__main__":
    main()
