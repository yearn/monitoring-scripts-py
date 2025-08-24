from datetime import datetime

from web3 import Web3

from utils.abi import load_abi
from utils.cache import get_last_executed_morpho_from_file, write_last_executed_morpho_to_file
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "MORPHO"
MORPHO_URL = "https://app.morpho.org"
COMPOUND_URL = "https://compound.blue"

PENDING_CAP_TYPE = "pending_cap"
REMOVABLE_AT_TYPE = "removable_at"

# Map vaults by chain
VAULTS_BY_CHAIN = {
    Chain.MAINNET: [
        ["Steakhouse USDC", "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"],
        ["Steakhouse USDT", "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa"],
        # ["Usual Boosted USDC", "0xd63070114470f685b75B74D60EEc7c1113d33a3D"],
        ["Gauntlet WETH Prime", "0x2371e134e3455e0593363cBF89d3b6cf53740618"],
        ["Gauntlet USDC Prime", "0xdd0f28e19C1780eb6396170735D45153D261490d"],
        ["Gauntlet USDT Prime", "0x8CB3649114051cA5119141a34C200D65dc0Faa73"],
        ["Gauntlet WETH Core", "0x4881Ef0BF6d2365D3dd6499ccd7532bcdBCE0658"],
        ["Gauntlet USDC Core", "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458"],
        ["Gauntlet DAI Core", "0x500331c9fF24D9d11aee6B07734Aa72343EA74a5"],
        ["VaultBridge USDC", "0xBEefb9f61CC44895d8AEc381373555a64191A9c4"],
        ["VaultBridge USDT", "0xc54b4E08C1Dcc199fdd35c6b5Ab589ffD3428a8d"],
        ["VaultBridge WETH", "0x31A5684983EeE865d943A696AAC155363bA024f9"],
        ["VaultBridge WBTC", "0x812B2C6Ab3f4471c0E43D4BB61098a9211017427"],
        # ["Gauntlet WBTC Core", "0x443df5eEE3196e9b2Dd77CaBd3eA76C3dee8f9b2"],
        # ["Gauntlet LRT Core", "0x7Db8c75A903d66D669b2002870975cc5aA842b6D"],
        # ["LlamaRisk crvUSD Vault", "0x67315dd969B8Cd3a3520C245837Bf71f54579C75"],
    ],
    Chain.BASE: [
        ["Moonwell Flagship USDC", "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca"],
        # NOTE: no funds in vaults below
        # ["Moonwell Flagship ETH", "0xa0E430870c4604CcfC7B38Ca7845B1FF653D0ff1"],
        # ["Moonwell Flagship EURC", "0xf24608E0CCb972b0b0f4A6446a0BBf58c701a026"],
        # ["Moonwell Frontier cbBTC", "0x543257eF2161176D7C8cD90BA65C2d4CaEF5a796"],
        # ["Seamless/Gauntlet USDC", "0x616a4E1db48e22028f6bbf20444Cd3b8e3273738"],
        # ["Seamless/Gauntlet WETH", "0x27D8c7273fd3fcC6956a0B370cE5Fd4A7fc65c18"],
        # ["Seamless/Gauntlet cbBTC", "0x5a47C803488FE2BB0A0EAaf346b420e4dF22F3C7"],
    ],
    Chain.POLYGON: [
        ["Compound WETH", "0xF5C81d25ee174d83f1FD202cA94AE6070d073cCF"],
        ["Compound USDC", "0x781FB7F6d845E3bE129289833b04d43Aa8558c42"],
        ["Compound USDT", "0xfD06859A671C21497a2EB8C5E3fEA48De924D6c8"],
    ],
    Chain.KATANA: [
        ["Gauntlet WBTC", "0xf243523996ADbb273F0B237B53f30017C4364bBC"],
        ["Gauntlet USDC", "0xE4248e2105508FcBad3fe95691551d1AF14015f7"],
        ["Gauntlet USDT", "0x1ecDC3F2B5E90bfB55fF45a7476FF98A8957388E"],
        ["Gauntlet WETH", "0xC5e7AB07030305fc925175b25B93b285d40dCdFf"],
        ["Steakhouse Prime USDC", "0x61D4F9D3797BA4dA152238c53a6f93Fb665C3c1d"],
    ],
}


ABI_MORPHO = load_abi("morpho/abi/morpho.json")


def get_chain_name(chain: Chain):
    if chain == Chain.MAINNET:
        return "ethereum"
    else:
        return chain.name.lower()


def get_market_url(market, chain: Chain):
    if chain == Chain.POLYGON:
        return f"{COMPOUND_URL}/borrow/{market}"
    else:
        return f"{MORPHO_URL}/{get_chain_name(chain)}/market/{market}"


def get_vault_url_by_name(vault_name, chain: Chain):
    vaults = VAULTS_BY_CHAIN[chain]
    for name, address in vaults:
        if name == vault_name:
            if chain == Chain.POLYGON:
                return f"{COMPOUND_URL}/{address}"
            else:
                return f"{MORPHO_URL}/{get_chain_name(chain)}/vault/{address}"
    return None


def check_markets_pending_cap(name, morpho_contract, chain, w3):
    with w3.batch_requests() as batch:
        batch.add(morpho_contract.functions.supplyQueueLength())
        batch.add(morpho_contract.functions.withdrawQueueLength())

        length_responses = w3.execute_batch(batch)
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
        market_responses = w3.execute_batch(batch)
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
        pending_cap_and_config_responses = w3.execute_batch(batch)
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

            last_executed_morpho = get_last_executed_morpho_from_file(vault_address, market, PENDING_CAP_TYPE)

            if pending_cap_timestamp > last_executed_morpho:
                difference_in_percentage = ((pending_cap_value - current_cap) / current_cap) * 100
                time = datetime.fromtimestamp(pending_cap_timestamp).strftime("%Y-%m-%d %H:%M:%S")
                send_telegram_message(
                    f"Updating cap to new cap {pending_cap_value}, current cap {current_cap}, difference: {difference_in_percentage:.2f}%. \nFor vault [{name}]({vault_url}) for market: [{market}]({market_url}) on {chain.name}. Queued for {time}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(vault_address, market, PENDING_CAP_TYPE, pending_cap_timestamp)
            else:
                print(
                    f"Skipping pending cap update for vault {name}({vault_url}) for market: {market_url} because it was already executed"
                )

        # removable_at check
        removable_at = config[2]  # removable_at value is at index 2 in config struct
        if removable_at > 0:
            if removable_at > get_last_executed_morpho_from_file(vault_address, market, REMOVABLE_AT_TYPE):
                time = datetime.fromtimestamp(removable_at).strftime("%Y-%m-%d %H:%M:%S")
                send_telegram_message(
                    f"Vault [{name}]({vault_url}) queued to remove market: [{market}]({market_url}) at {time}",
                    PROTOCOL,
                )
                write_last_executed_morpho_to_file(vault_address, market, REMOVABLE_AT_TYPE, removable_at)
            else:
                print(
                    f"Skipping removable_at update for vault {name}({vault_url}) for market: {market_url} because it was already executed"
                )


def check_pending_role_change(name, morpho_contract, role_type, timestamp, chain):
    market_id = ""  # use empty string for all markets because the value is used per vault
    if timestamp > get_last_executed_morpho_from_file(morpho_contract.address, market_id, role_type):
        vault_url = get_vault_url_by_name(name, chain)
        send_telegram_message(
            f"{role_type.capitalize()} is changing for vault [{name}]({vault_url})",
            PROTOCOL,
        )
        write_last_executed_morpho_to_file(morpho_contract.address, market_id, role_type, timestamp)


def check_timelock_and_guardian(name, morpho_contract, chain, client):
    with morpho_contract.w3.batch_requests() as batch:
        batch.add(morpho_contract.functions.pendingTimelock())
        batch.add(morpho_contract.functions.pendingGuardian())
        responses = client.execute_batch(batch)
        if len(responses) != 2:
            raise ValueError("Expected 2 responses from batch, got: ", len(responses))

        timelock = responses[0][1]  # [1] to get the timestamp
        guardian = responses[1][1]  # [1] to get the timestamp

    check_pending_role_change(name, morpho_contract, "timelock", timelock, chain)
    check_pending_role_change(name, morpho_contract, "guardian", guardian, chain)


def get_data_for_chain(chain: Chain):
    client = ChainManager.get_client(chain)
    vaults = VAULTS_BY_CHAIN[chain]

    print(f"Processing Morpho Vaults on {chain.name} ...")
    print(f"Vaults: {vaults}")

    for vault in vaults:
        morpho_contract = client.eth.contract(address=vault[1], abi=ABI_MORPHO)
        check_markets_pending_cap(vault[0], morpho_contract, chain, client)
        check_timelock_and_guardian(vault[0], morpho_contract, chain, client)


def main():
    get_data_for_chain(Chain.MAINNET)
    get_data_for_chain(Chain.POLYGON)
    get_data_for_chain(Chain.KATANA)
    get_data_for_chain(Chain.BASE)


if __name__ == "__main__":
    main()
