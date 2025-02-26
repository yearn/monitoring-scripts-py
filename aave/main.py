import json

from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "aave"


# Load ABI
def load_abi(file_path):
    with open(file_path) as f:
        abi_data = json.load(f)
        if isinstance(abi_data, dict):
            return abi_data["result"]
        elif isinstance(abi_data, list):
            return abi_data
        else:
            raise ValueError("Invalid ABI format")


ABI_ATOKEN = load_abi("aave/abi/AToken.json")

# Map addresses and symbols by chain
ADDRESSES_BY_CHAIN = {
    Chain.POLYGON: [
        # aToken, underlying, symbol
        ("0x625E7708f30cA75bfd92586e17077590C60eb4cD", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "USDC.e"),
        ("0xA4D94019934D8333Ef880ABFFbF2FDd611C762BD", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "USDC"),
        ("0x6ab707Aca953eDAeFBc4fD23bA73294241490620", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "USDT"),
        ("0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE", "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", "DAI"),
        ("0x6d80113e533a2C0fe82EaBD35f1875DcEA89Ea97", "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "MATIC"),
        ("0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8", "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", "WETH"),
    ],
    Chain.MAINNET: [
        ("0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "WETH"),
        ("0x23878914EFE38d27C4D67Ab83ed1b93A74D4086a", "0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT"),
        ("0x98C23E9d8f34FEFb1B7BD6a91B7FF122F4e16F5c", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC"),
        ("0x018008bfb33d285247A21d44E50697654f754e63", "0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI"),
        ("0xb82fa9f31612989525992FCfBB09AB22Eff5c85A", "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E", "crvUSD"),
    ],
    Chain.ARBITRUM: [
        ("0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "WETH"),
        ("0x724dc807b04555b71ed48a6896b6F41593b8C637", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "USDC"),
        ("0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE", "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", "DAI"),
        ("0x625E7708f30cA75bfd92586e17077590C60eb4cD", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", "USDC.e"),
        ("0x6ab707Aca953eDAeFBc4fD23bA73294241490620", "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "USDT"),
        ("0x6533afac2E7BCCB20dca161449A13A32D391fb00", "0x912CE59144191C1204E64559FE8253a0e49E6548", "ARB"),
    ],
    # We don't use optimism - add if needed
    # Chain.OPTIMISM: [
    #     "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8",  # aweth
    #     "0x4200000000000000000000000000000000000006",  # weth
    #     "0x38d693cE1dF5AaDF7bC62595A37D667aD57922e5",  # ausdc
    #     "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",  # usdc
    #     "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE",  # adai
    #     "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",  # dai
    #     "0x625E7708f30cA75bfd92586e17077590C60eb4cD",  # ausdc.e
    #     "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",  # usdc.e
    #     "0x6ab707Aca953eDAeFBc4fD23bA73294241490620",  # ausdt
    #     "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",  # usdt
    #     "0x513c7E3a9c69cA3e22550eF58AC1C0088e918FFf",  # aop
    #     "0x4200000000000000000000000000000000000042",  # op
    # ]
}

THRESHOLD_UR = 0.99
THRESHOLD_UR_NOTIFICATION = 0.99


def print_stuff(chain_name, token_name, ur):
    if ur > THRESHOLD_UR:
        message = (
            "🚨 **BEEP BOP** 🚨\n"
            f"💎 Market asset: {token_name}\n"
            f"📊 Utilization rate: {ur:.2%}\n"
            f"🌐 Chain: {chain_name}"
        )
        disable_notification = True
        if ur > THRESHOLD_UR_NOTIFICATION:
            disable_notification = False
        send_telegram_message(message, PROTOCOL, disable_notification)


def process_assets(chain: Chain):
    client = ChainManager.get_client(chain)
    addresses = ADDRESSES_BY_CHAIN[chain]

    # Prepare all contracts and batch calls
    contracts = []
    with client.batch_requests() as batch:
        for atoken_address, underlying_token_address, token_symbol in addresses:
            atoken = client.eth.contract(address=atoken_address, abi=ABI_ATOKEN)
            underlying_token = client.eth.contract(
                address=underlying_token_address, abi=ABI_ATOKEN
            )
            contracts.append((atoken, underlying_token))

            batch.add(atoken.functions.totalSupply())
            batch.add(underlying_token.functions.balanceOf(atoken_address))

        responses = client.execute_batch(batch)
        num_pairs = len(addresses)
        expected_responses = num_pairs * 2  # Now only 2 calls per token pair
        if len(responses) != expected_responses:
            raise ValueError(
                f"Expected {expected_responses} responses from batch, got: {len(responses)}"
            )

    # Process results
    for i, (_, _, token_symbol) in enumerate(addresses):
        ts = responses[i * 2]  # totalSupply
        av = responses[i * 2 + 1]  # balanceOf

        debt = ts - av
        ur = debt / ts if ts != 0 else 0

        print_stuff(chain.name, token_symbol, ur)


def main():
    for chain in [Chain.MAINNET, Chain.POLYGON, Chain.ARBITRUM]:
        print(f"Processing {chain.name} assets...")
        process_assets(chain)


if __name__ == "__main__":
    main()
