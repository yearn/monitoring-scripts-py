from utils.abi import load_abi
from utils.chains import Chain
from utils.gauntlet import fetch_borrow_metrics_from_gauntlet
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "comp"
logger = get_logger(PROTOCOL)
THRESHOLD_UR = 0.99
THRESHOLD_UR_NOTIFICATION = 0.99

ABI_CTOKEN = load_abi("compound/abi/CTokenV3.json")

# Map addresses by chain: list of (address, name) tuples
ADDRESSES_BY_CHAIN = {
    Chain.MAINNET: [
        ("0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840", "cUSDTv3"),
        ("0xc3d688B66703497DAA19211EEdff47f25384cdc3", "cUSDCv3"),
        ("0xA17581A9E3356d9A858b789D68B4d866e593aE94", "cWETHv3"),
    ],
}
COMPOUND_VAULTS_KEYS = [
    # Gauntlet tag, Risk level
    ["v3-ethereum-usdc", 1],
    ["v3-ethereum-usdt", 1],
    ["v3-ethereum-weth", 1],
    # ["v3-ethereum-wbtc", 1],
    # ["v3-ethereum-wsteth", 1],
    ["v3-ethereum-usds", 2],
    # NOTE: polygon data can be stale, so we don't monitor it
    # ["v3-polygon-usdc", 1],
    # ["v3-polygon-usdt", 1],
]


def print_stuff(chain_name: str, token_name: str, ur: float) -> None:
    logger.debug(f"Chain: {chain_name}, Token: {token_name}, UR: {ur}")
    if ur > THRESHOLD_UR:
        message = (
            f"🚨 **BEEP BOP** 🚨\n💎 Market asset: {token_name}\n📊 Utilization rate: {ur:.2%}\n🌐 Chain: {chain_name}"
        )
        disable_notification = True if ur <= THRESHOLD_UR_NOTIFICATION else False
        send_telegram_message(message, PROTOCOL, disable_notification)


def process_assets(chain: Chain) -> None:
    client = ChainManager.get_client(chain)
    addresses = ADDRESSES_BY_CHAIN[chain]

    with client.batch_requests() as batch:
        for ctoken_address, _ in addresses:
            ctoken = client.eth.contract(address=ctoken_address, abi=ABI_CTOKEN)
            batch.add(ctoken.functions.getUtilization())

        responses = client.execute_batch(batch)
        if len(responses) != len(addresses):
            raise ValueError(f"Expected {len(addresses)} responses from batch, got: {len(responses)}")

    for (_, ctoken_name), response in zip(addresses, responses):
        ur = int(response) / 1e18
        print_stuff(chain.name, ctoken_name, ur)


def analyze_compound_market_allocation(market_key, vault_risk_level=1):
    """Analyze Compound market allocation using Gauntlet and send alerts if needed"""
    alerts = fetch_borrow_metrics_from_gauntlet("compound", market_key, vault_risk_level)
    if alerts:
        message = "\n\n".join(alerts)
        send_telegram_message(message, PROTOCOL)


def main():
    for chain in [Chain.MAINNET]:
        logger.info("Processing %s assets...", chain.name)
        process_assets(chain)

    for market_key, vault_risk_level in COMPOUND_VAULTS_KEYS:
        analyze_compound_market_allocation(market_key, vault_risk_level)


if __name__ == "__main__":
    main()
