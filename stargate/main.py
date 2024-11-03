from web3 import Web3, constants
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message

load_dotenv()

PROTOCOL = "STARGATE"
provider_url_polygon = os.getenv("PROVIDER_URL")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")

with open("common-abi/Strategy.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_strategy = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_strategy = abi_data

# Add only strategies that are used by Vaults
polygon_strategies = [
    "0x8BBa7AFd0f9B1b664C161EC31d812a8Ec15f7e1a",  # stargate staker usdc.e strategy
    "0x2c5d0c3DB75D2f8A4957c74BE09194a9271Cf28D",  # stargate staker usdt strategy
    # Add more pairs as needed
]

arbitrum_strategies = [
    # Add more pairs as needed
]

buffer = 0.1


def print_stuff(
    total_debt,
    net_room,
    total_idle,
    strategy_name,
    underlying_token_decimals,
    chain_name,
):

    total_debt /= 10**underlying_token_decimals
    net_room /= 10**underlying_token_decimals
    total_idle /= 10**underlying_token_decimals

    message = (
        "🚨 **DANGER** 🚨\n"
        f"🌟 Stargate withdraw room: {net_room:.3f}\n"
        f"💰 Total assets idle in strategy: {total_idle:.3f}\n"
        f"📈 Total assets deposited in stargate: {total_debt:.3f}\n"
        f"🔍 Strategy name: {strategy_name}\n"
        f"🌐 Chain: {chain_name}"
    )
    send_telegram_message(message, PROTOCOL)


# Wrap address to Strategy contract
def wrap_address_to_contract(address, provider_url):
    w3 = Web3(Web3.HTTPProvider(provider_url))
    contract = w3.eth.contract(address=address, abi=abi_strategy)
    return contract


# Function to process assets for a specific network
def process_assets(chain_name, strategies, provider_url):
    ## loop through all the strategies
    for strategy_address in strategies:
        # Build contracts
        strategy = wrap_address_to_contract(strategy_address, provider_url)
        underlying_token = wrap_address_to_contract(
            strategy.functions.asset().call(), provider_url
        )

        # Get total supply and available balance
        withdraw_room = strategy.functions.availableWithdrawLimit(
            constants.ADDRESS_ZERO
        ).call()
        total_idle = underlying_token.functions.balanceOf(strategy.address).call()
        net_room = withdraw_room - total_idle

        total_assets = strategy.functions.totalAssets().call()
        total_debt = total_assets - total_idle

        if total_debt * (1 + buffer) > net_room:
            strategy_name = strategy.functions.name().call()
            underlying_token_decimals = strategy.functions.decimals().call()
            print_stuff(
                int(total_debt),
                int(net_room),
                int(total_idle),
                strategy_name,
                int(underlying_token_decimals),
                chain_name,
            )


def main():
    print("Processing Polygon assets...")
    process_assets("Polygon", polygon_strategies, provider_url_polygon)

    print("Processing Arbitrum assets...")
    process_assets("Arbitrum", arbitrum_strategies, provider_url_arb)


if __name__ == "__main__":
    main()
