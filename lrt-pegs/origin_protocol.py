from utils.abi import load_abi
from utils.cache import get_last_queued_id_from_file, write_last_queued_id_to_file
from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

REDEEM_VAULE = 1e18
PROTOCOL = "pegs"
logger = get_logger("lrt-pegs.origin")

# Load Origin Vault ABI
ABI_ORIGIN_VAULT = load_abi("lrt-pegs/abi/OriginVault.json")
ABI_ORIGIN_WRAPPED_OETH = load_abi("common-abi/YearnV3Vault.json")

ORIGIN_CONFIGS = {
    Chain.BASE: {
        "vault_address": "0x98a0CbeF61bD2D21435f433bE4CD42B56B38CC93",
        "eth_address": "0x4200000000000000000000000000000000000006",
        "wrapped_oeth_address": "0x7FcD174E80f264448ebeE8c88a7C4476AAF58Ea6",
    },
    Chain.MAINNET: {
        "vault_address": "0x39254033945AA2E4809Cc2977E7087BEE48bd7Ab",
        "eth_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "wrapped_oeth_address": "0xDcEe70654261AF21C44c093C300eD3Bb97b78192",
    },
}


def get_cache_key(chain: Chain) -> str:
    """Get cache key for redeem value on this chain."""
    return f"origin_redeem_{chain.network_name}"


def process_origin(chain: Chain):
    """
    Monitor Origin Protocol metrics on the specified chain.

    OETH redeem value is 1e18, 1-to-1 with ETH.
    Wrapped OETH redeem value should only go up, if it goes down, it is a sign of protocol health issue.

    Args:
        chain: The blockchain to monitor (BASE or MAINNET)
    """
    config = ORIGIN_CONFIGS[chain]
    client = ChainManager.get_client(chain)
    vault = client.eth.contract(address=config["vault_address"], abi=ABI_ORIGIN_VAULT)
    wrapped_oeth = client.eth.contract(address=config["wrapped_oeth_address"], abi=ABI_ORIGIN_WRAPPED_OETH)

    with client.batch_requests() as batch:
        batch.add(vault.functions.priceUnitRedeem(config["eth_address"]))
        batch.add(wrapped_oeth.functions.convertToAssets(int(1e18)))
        responses = client.execute_batch(batch)
        if len(responses) != 2:
            send_telegram_message(
                f"🚨 Origin Protocol Alert! Expected 2 responses from batch, got: {len(responses)}",
                PROTOCOL,
                True,
            )

        redeem_value = responses[0]
        wrapped_oeth_redeem_value = responses[1]

        logger.info("Redeem value for wsuperOETH on %s: %s", chain.name, f"{redeem_value / 1e18:.2f}")
        logger.info("Wrapped OETH redeem value: %s", f"{wrapped_oeth_redeem_value / 1e18:.2f}")

        # Caching for the redeem value, if the redeem value is lower, send telegram message
        cache_key = get_cache_key(chain)
        cached_redeem_value = get_last_queued_id_from_file(cache_key)

        if wrapped_oeth_redeem_value == 0:
            logger.info(
                "[%s] Saving initial redeem value to cache: %s",
                chain.network_name,
                f"{wrapped_oeth_redeem_value / 1e18:.2f}",
            )
        elif wrapped_oeth_redeem_value < cached_redeem_value:
            message = (
                f"🚨 *Origin Protocol {chain.network_name.upper()} Alert* 🚨\n"
                f"🔍 Redeem value dropped!\n"
                f"Current Redeem Value: {wrapped_oeth_redeem_value / 1e18:.2f}\n"
                f"Previous Redeem Value: {cached_redeem_value / 1e18:.2f}\n"
                f"Difference: {cached_redeem_value - wrapped_oeth_redeem_value} ({((cached_redeem_value - wrapped_oeth_redeem_value) / cached_redeem_value) * 100:.2f}%)"
            )
            send_telegram_message(message, PROTOCOL)

        write_last_queued_id_to_file(cache_key, wrapped_oeth_redeem_value)

        if redeem_value != REDEEM_VAULE:
            message = f"🚨 Origin Protocol Alert! Redeem value for wsuperOETH on {chain.name} is different frrom 1e18: {redeem_value}"
            send_telegram_message(message, PROTOCOL)


def main():
    logger.info("Checking Origin Protocol on Base...")
    process_origin(Chain.BASE)
    logger.info("Checking Origin Protocol on Mainnet...")
    process_origin(Chain.MAINNET)
    # NOTE: no need to check liquidity on Base because pool is concentrated around 1 tick and by pool with the highest liquidity on Base
    # docs: https://docs.originprotocol.com/yield-bearing-tokens/core-concepts/amo


if __name__ == "__main__":
    main()
