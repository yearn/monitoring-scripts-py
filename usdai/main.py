import datetime
import requests
from web3 import Web3

from utils.abi import load_abi
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.config import Config
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager


# Constants
PROTOCOL = "usdai"
VAULT_ADDR = Web3.to_checksum_address("0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF")
WM_TOKEN = Web3.to_checksum_address("0x437cc33344a0b27a429f795ff6b469c72698b291")
SUSDAI_ADDR = Web3.to_checksum_address("0x0B2b2B2076d95dda7817e785989fE353fe955ef9")
GRAPHQL_URL = "https://protocol-api.m0.org/graphql"


LOAN_ROUTER_ADDR = Web3.to_checksum_address("0x0C2ED170F2bB1DF1a44292Ad621B577b3C9597D1")

def get_loan_details(client, owner_addr):
    """
    Reads active loan NFTs held by the owner.
    Returns list of (token_id, principal, maturity).
    """
    loans = []
    try:
        # Minimal ABI for ERC721 Enumerable + raw call for loanState
        abi = [
            {"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
            {"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
        ]
        router = client.get_contract(LOAN_ROUTER_ADDR, abi)
        count = router.functions.balanceOf(owner_addr).call()
        
        for i in range(count):
            token_id = router.functions.tokenOfOwnerByIndex(owner_addr, i).call()
            
            # Raw call to loanState(uint256) -> signature 0x0d92c757
            selector = Web3.keccak(text="loanState(uint256)")[:4].hex()
            data = selector + int(token_id).to_bytes(32, 'big').hex()
            
            raw_res = client.eth.call({"to": LOAN_ROUTER_ADDR, "data": data})
            
            # Decode: we found the structure is likely:
            # 0: State (uint256)
            # 1: Maturity Timestamp (uint256)
            # 2: Start Timestamp (uint256)
            # 3: Principal (uint256)
            
            if len(raw_res) >= 128: # At least 4 words
                # skip 0-32 (state), read 32-64 (maturity)
                maturity = int.from_bytes(raw_res[32:64], 'big')
                # skip 64-96 (start), read 96-128 (principal)
                principal = int.from_bytes(raw_res[96:128], 'big')
                
                loans.append({
                    "id": token_id,
                    "principal": principal / 1e18,
                    "maturity": maturity
                })
                
    except Exception as e:
        print(f"Loan scan error: {e}")
        
    return loans

def main():
    client = ChainManager.get_client(Chain.ARBITRUM)

    # Common ABI
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
            res = requests.post(GRAPHQL_URL, json={"query": query}, timeout=Config.get_request_timeout())
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

        # --- sUSDai Monitoring (GPU Loans) ---
        
        try:
            # 4. Scan Individual Loan NFTs
            # Scan sUSDai Vault
            all_loans = get_loan_details(client, SUSDAI_ADDR)
            
            # --- Manual Adjustment for Legacy Loan ---
            # There is one active loan (NVIDIA H200s) originated before the Loan Router deployment.
            # Principal: ~$560k (Remaining Principal from UI: $559,542)
            # We hardcode this to ensure accurate Total Principal tracking.
            legacy_loan_principal = 559_542.00
            
            if all_loans or legacy_loan_principal > 0:
                print("\n--- Active Loan NFTs (Direct Read) ---")
                total_verified_principal = 0
                
                # Add Legacy Loan
                print(f"Legacy Loan (H200s): ${legacy_loan_principal:,.2f} (Hardcoded)")
                total_verified_principal += legacy_loan_principal
                
                for l in all_loans:
                    mat_date = datetime.datetime.fromtimestamp(l['maturity']).strftime('%Y-%m-%d')
                    print(f"Loan #{l['id'] % 10000:04d}...: ${l['principal']:,.2f} (Mat: {mat_date})")
                    total_verified_principal += l['principal']
                
                print(f"Total Verified Principal: ${total_verified_principal:,.2f}")
                
                # Calculate Ratio to Total Supply
                verified_ratio = (total_verified_principal / usdai_supply_fmt * 100) if usdai_supply_fmt > 0 else 0
                print(f"Verified Loan Ratio: {verified_ratio:.2f}% of Total Supply")

                # --- Alerting on Principal Change ---
                cache_key_principal = f"{PROTOCOL}_verified_principal"
                last_principal = float(get_last_value_for_key_from_file(cache_filename, cache_key_principal))
                
                # Check for change (allow small dust difference < $1.00)
                if last_principal != 0 and abs(total_verified_principal - last_principal) > 1.0:
                    change_type = "increased (New Loan)" if total_verified_principal > last_principal else "reduced (Repayment)"
                    diff = abs(total_verified_principal - last_principal)
                    
                    msg = (
                        f"📢 *sUSDai Loan Activity*\n\n"
                        f"Total Verified Principal has {change_type}.\n"
                        f"Change: ${diff:,.2f}\n"
                        f"Old Total: ${last_principal:,.2f}\n"
                        f"New Total: ${total_verified_principal:,.2f}\n"
                        f"Current Ratio: {verified_ratio:.2f}% of Supply"
                    )
                    send_telegram_message(msg, PROTOCOL)
                
                # Update cache
                write_last_value_to_file(cache_filename, cache_key_principal, total_verified_principal)

        except Exception as e:
            print(f"sUSDai Monitoring Error: {e}")

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
