import requests
from dotenv import load_dotenv
from web3 import Web3

from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

load_dotenv()

# Constants
PROTOCOL = "usdai"
VAULT_ADDR = Web3.to_checksum_address("0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF")
WM_TOKEN = Web3.to_checksum_address("0x437cc33344a0b27a429f795ff6b469c72698b291")
SUSDAI_ADDR = Web3.to_checksum_address("0x0B2b2B2076d95dda7817e785989fE353fe955ef9")
GRAPHQL_URL = "https://protocol-api.m0.org/graphql"


def main():
    client = ChainManager.get_client(Chain.ARBITRUM)

    # Common ABI
    from utils.abi import load_abi

    erc20_abi = load_abi("common-abi/ERC20.json")

    wm = client.get_contract(WM_TOKEN, erc20_abi)

    try:
        # --- On-Chain Supply ---
        # USDai Supply (wM held by Vault)
        vault_shares = wm.functions.balanceOf(VAULT_ADDR).call()
        # Decimals will always be the same = 6
        wm_decimals = 6
        usdai_supply_fmt = vault_shares / (10**wm_decimals)

        # 2. Get Mint Ratio via API
        query = """
        query {
          mintRatio: protocolConfigs(
            where: {key: "mint_ratio"}
            orderBy: blockTimestamp
            orderDirection: desc
            first: 1
          ) {
            value
            blockTimestamp
          }
        }
        """

        mint_ratio = 10000  # Default to 1:1 (scaled 1e4 for bps) if not found

        try:
            res = requests.post(GRAPHQL_URL, json={"query": query}, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", {})

                # --- Mint Ratio ---
                configs = data.get("mintRatio", [])
                if configs:
                    # Mint ratio is scaled by 1e4 (e.g. 9950 = 99.5%)
                    mint_ratio_raw = int(configs[0].get("value", 10000))
                    mint_ratio = mint_ratio_raw

        except Exception as e:
            print(f"API Error: {e}")

        # Derived Collateral from Mint Ratio
        # Scaling: mint_ratio is in bps (1e4).
        # So mint_ratio_fmt = mint_ratio / 10000.
        mint_ratio_fmt = mint_ratio / 10000

        # Avoid division by zero
        required_collateral = 0
        if mint_ratio_fmt > 0:
            required_collateral = usdai_supply_fmt / mint_ratio_fmt

        print("\n--- USDai Stats ---")
        print(f"USDai Supply:    ${usdai_supply_fmt:,.2f}")
        print(f"Mint Ratio:      {mint_ratio_fmt:.4f}")

        collateral_metric = required_collateral
        # Buffer = Collateral - Supply
        buffer = collateral_metric - usdai_supply_fmt

        print(f"Collateral:      ${collateral_metric:,.2f}")
        print(f"Buffer:          ${buffer:,.2f}")

        if collateral_metric > 0:
            # 1. Check for Mint Ratio Change (Critical)
            cache_key_ratio = f"{PROTOCOL}_mint_ratio"
            last_ratio = int(get_last_value_for_key_from_file(cache_filename, cache_key_ratio))

            if last_ratio != 0 and last_ratio != mint_ratio:
                msg = f"⚠️ *USDai Mint Ratio Changed*\n\nOld: {last_ratio / 10000:.4f}\nNew: {mint_ratio / 10000:.4f}"
                send_telegram_message(msg, PROTOCOL)

            # Always update ratio cache
            write_last_value_to_file(cache_filename, cache_key_ratio, mint_ratio)

            # 2. Check for Low Buffer (ignore withdrawals)
            cache_key_buffer = f"{PROTOCOL}_buffer"
            last_buffer = float(get_last_value_for_key_from_file(cache_filename, cache_key_buffer))

            # Only alert when buffer drops below $1,000,000
            buffer_alert_threshold = 1_000_000
            if last_buffer != 0:
                crossed_below = last_buffer >= buffer_alert_threshold and buffer < buffer_alert_threshold
                if crossed_below:
                    msg = (
                        "📉 *USDai Low Buffer Alert*\n\n"
                        f"Buffer dropped below ${buffer_alert_threshold:,.0f}.\n"
                        f"Old Buffer: ${last_buffer:,.2f}\n"
                        f"New Buffer: ${buffer:,.2f}\n"
                        f"(Collateral: ${collateral_metric:,.2f})"
                    )
                    send_telegram_message(msg, PROTOCOL)

            write_last_value_to_file(cache_filename, cache_key_buffer, buffer)

    except Exception as e:
        print(f"Error: {e}")
        send_telegram_message(f"⚠️ USDai monitoring failed: {e}", PROTOCOL, False, True)


if __name__ == "__main__":
    main()
