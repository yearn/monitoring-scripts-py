import datetime
import os

import requests
from web3 import Web3

from utils.abi import load_abi
from utils.alert import Alert, AlertSeverity, send_alert
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.config import Config
from utils.defillama import fetch_prices
from utils.logging import get_logger
from utils.web3_wrapper import ChainManager

# Constants
PROTOCOL = "usdai"
logger = get_logger(PROTOCOL)

USDAI_VAULT_ADDR = Web3.to_checksum_address("0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF")
PYUSD_TOKEN_ADDR = Web3.to_checksum_address("0x46850aD61C2B7d64d08c9C754F45254596696984")
SUSDAI_ADDR = Web3.to_checksum_address("0x0B2b2B2076d95dda7817e785989fE353fe955ef9")
LOAN_ROUTER_ADDR = Web3.to_checksum_address("0x0C2ED170F2bB1DF1a44292Ad621B577b3C9597D1")
ARBISCAN_TOKEN_API_URL = "https://api.etherscan.io/v2/api"

# Alert thresholds (absolute deviation from 1.0)
# Raised defaults to reduce alert noise; still overrideable via env vars.
USDAI_PYUSD_WARN_DEVIATION = Config.get_env_float("USDAI_PYUSD_WARN_DEVIATION", 0.003)  # 0.30%
USDAI_PYUSD_CRITICAL_DEVIATION = Config.get_env_float("USDAI_PYUSD_CRITICAL_DEVIATION", 0.01)  # 1.00%
PYUSD_USD_WARN_DEVIATION = Config.get_env_float("PYUSD_USD_WARN_DEVIATION", 0.003)  # 0.30%
PYUSD_USD_CRITICAL_DEVIATION = Config.get_env_float("PYUSD_USD_CRITICAL_DEVIATION", 0.0075)  # 0.75%


def send_breach_alert_once(cache_key, alert_message, severity=AlertSeverity.HIGH):
    last_state = int(get_last_value_for_key_from_file(cache_filename, cache_key))
    if last_state == 0:
        send_alert(Alert(severity, alert_message, PROTOCOL))
        write_last_value_to_file(cache_filename, cache_key, 1)


def clear_breach_state(cache_key):
    last_state = int(get_last_value_for_key_from_file(cache_filename, cache_key))
    if last_state == 1:
        write_last_value_to_file(cache_filename, cache_key, 0)


def get_usdai_supply_from_arbiscan(decimals: int) -> float | None:
    api_key = os.getenv("ARBISCAN_TOKEN") or os.getenv("ETHERSCAN_TOKEN")
    if not api_key:
        logger.warning("ARBISCAN_TOKEN/ETHERSCAN_TOKEN not set; cannot fetch USDai supply from Arbiscan API.")
        return None

    params = {
        "chainid": Chain.ARBITRUM.chain_id,
        "module": "stats",
        "action": "tokensupply",
        "contractaddress": USDAI_VAULT_ADDR,
        "apikey": api_key,
    }

    try:
        res = requests.get(ARBISCAN_TOKEN_API_URL, params=params, timeout=Config.get_request_timeout())
        if res.status_code != 200:
            logger.warning("Arbiscan API returned non-200 for USDai supply: %s", res.status_code)
            return None

        payload = res.json()
        status = str(payload.get("status", "0"))
        raw_supply = payload.get("result")
        if status != "1" or not str(raw_supply).isdigit():
            logger.warning("Arbiscan API returned unexpected payload for USDai supply: %s", payload)
            return None

        return int(raw_supply) / (10**decimals)
    except Exception as exc:
        logger.warning("Failed to fetch USDai supply from Arbiscan API: %s", exc)
        return None


def get_loan_details(client, owner_addr):
    """
    Reads active loan NFTs held by the owner.
    Returns list of (token_id, principal, maturity).
    """
    loans = []
    try:
        abi = load_abi("common-abi/LoanRouter.json")
        router = client.get_contract(LOAN_ROUTER_ADDR, abi)
        count = router.functions.balanceOf(owner_addr).call()

        if count > 0:
            # 1. Get all token IDs
            with client.batch_requests() as batch:
                for i in range(count):
                    batch.add(router.functions.tokenOfOwnerByIndex(owner_addr, i))

                token_ids = client.execute_batch(batch)

            # 2. Get Loan States
            with client.batch_requests() as batch:
                for token_id in token_ids:
                    batch.add(router.functions.loanState(token_id))

                loan_states = client.execute_batch(batch)

            for token_id, state_tuple in zip(token_ids, loan_states):
                # state_tuple: (state, maturity, start, principal)
                # We need maturity (index 1) and principal (index 3)
                if state_tuple and len(state_tuple) >= 4:
                    maturity = state_tuple[1]
                    principal = state_tuple[3]
                    loans.append({"id": token_id, "principal": principal / 1e18, "maturity": maturity})

    except Exception as e:
        logger.error("Loan scan error: %s", e)
        send_alert(Alert(AlertSeverity.LOW, f"Loan scan error: {e}", PROTOCOL), plain_text=True)

    return loans


def main():
    client = ChainManager.get_client(Chain.ARBITRUM)

    # Common ABI
    erc20_abi = load_abi("common-abi/ERC20.json")

    usdai = client.get_contract(USDAI_VAULT_ADDR, erc20_abi)
    pyusd = client.get_contract(PYUSD_TOKEN_ADDR, erc20_abi)

    try:
        # --- 1) USDai / pyUSD Backing Ratio ---
        with client.batch_requests() as batch:
            batch.add(usdai.functions.decimals())
            batch.add(pyusd.functions.decimals())
            batch.add(pyusd.functions.symbol())
            batch.add(pyusd.functions.balanceOf(USDAI_VAULT_ADDR))
            usdai_decimals, pyusd_decimals, pyusd_symbol, pyusd_assets_raw = client.execute_batch(batch)

        usdai_supply_fmt = get_usdai_supply_from_arbiscan(usdai_decimals)
        supply_source = "Arbiscan API"
        if usdai_supply_fmt is None:
            usdai_supply_raw = usdai.functions.totalSupply().call()
            usdai_supply_fmt = usdai_supply_raw / (10**usdai_decimals)
            supply_source = "on-chain totalSupply fallback"

        pyusd_assets_fmt = pyusd_assets_raw / (10**pyusd_decimals)
        backing_ratio = (pyusd_assets_fmt / usdai_supply_fmt) if usdai_supply_fmt > 0 else 0
        backing_deviation = abs(backing_ratio - 1)

        logger.info("--- USDai Stats ---")
        logger.info("USDai Supply:    $%s", f"{usdai_supply_fmt:,.2f}")
        logger.info("Supply Source:   %s", supply_source)
        logger.info("%s Assets:    $%s", pyusd_symbol, f"{pyusd_assets_fmt:,.2f}")
        logger.info("Backing Ratio:   %s %s / USDai", f"{backing_ratio:.6f}", pyusd_symbol)

        cache_key_backing_warn = f"{PROTOCOL}_backing_ratio_warn_breach"
        cache_key_backing_critical = f"{PROTOCOL}_backing_ratio_critical_breach"

        if usdai_supply_fmt > 0:
            if backing_deviation >= USDAI_PYUSD_CRITICAL_DEVIATION:
                send_breach_alert_once(
                    cache_key=cache_key_backing_critical,
                    severity=AlertSeverity.CRITICAL,
                    alert_message=(
                        "*USDai Backing Ratio Critical*\n\n"
                        f"{pyusd_symbol} per USDai: {backing_ratio:.6f}\n"
                        f"Deviation from 1.0: {backing_deviation:.3%}\n"
                        f"{pyusd_symbol} Assets: ${pyusd_assets_fmt:,.2f}\n"
                        f"USDai Supply: ${usdai_supply_fmt:,.2f}"
                    ),
                )
            else:
                clear_breach_state(cache_key_backing_critical)

            if USDAI_PYUSD_WARN_DEVIATION <= backing_deviation < USDAI_PYUSD_CRITICAL_DEVIATION:
                send_breach_alert_once(
                    cache_key=cache_key_backing_warn,
                    severity=AlertSeverity.HIGH,
                    alert_message=(
                        "*USDai Backing Ratio Alert*\n\n"
                        f"{pyusd_symbol} per USDai: {backing_ratio:.6f}\n"
                        f"Deviation from 1.0: {backing_deviation:.3%}\n"
                        f"{pyusd_symbol} Assets: ${pyusd_assets_fmt:,.2f}\n"
                        f"USDai Supply: ${usdai_supply_fmt:,.2f}"
                    ),
                )
            else:
                clear_breach_state(cache_key_backing_warn)

        # --- 2) pyUSD / USD Peg ---
        pyusd_key = f"{Chain.ARBITRUM.network_name}:{PYUSD_TOKEN_ADDR.lower()}"
        pyusd_price = None
        try:
            prices = fetch_prices([pyusd_key])
            pyusd_price = prices.get(pyusd_key)
        except Exception as e:
            logger.error("pyUSD price fetch error: %s", e)

        if pyusd_price is not None:
            pyusd_price = float(pyusd_price)
            pyusd_price_deviation = abs(pyusd_price - 1)
            logger.info("%s / USD:      %s", pyusd_symbol, f"{pyusd_price:.6f}")

            cache_key_peg_warn = f"{PROTOCOL}_pyusd_peg_warn_breach"
            cache_key_peg_critical = f"{PROTOCOL}_pyusd_peg_critical_breach"

            if pyusd_price_deviation >= PYUSD_USD_CRITICAL_DEVIATION:
                send_breach_alert_once(
                    cache_key=cache_key_peg_critical,
                    severity=AlertSeverity.CRITICAL,
                    alert_message=(
                        f"*{pyusd_symbol}/USD Peg Critical*\n\n"
                        f"{pyusd_symbol}/USD: ${pyusd_price:.6f}\n"
                        f"Deviation from $1: {pyusd_price_deviation:.3%}"
                    ),
                )
            else:
                clear_breach_state(cache_key_peg_critical)

            if PYUSD_USD_WARN_DEVIATION <= pyusd_price_deviation < PYUSD_USD_CRITICAL_DEVIATION:
                send_breach_alert_once(
                    cache_key=cache_key_peg_warn,
                    severity=AlertSeverity.HIGH,
                    alert_message=(
                        f"*{pyusd_symbol}/USD Peg Alert*\n\n"
                        f"{pyusd_symbol}/USD: ${pyusd_price:.6f}\n"
                        f"Deviation from $1: {pyusd_price_deviation:.3%}"
                    ),
                )
            else:
                clear_breach_state(cache_key_peg_warn)
        else:
            logger.warning("No price returned for %s (%s)", pyusd_symbol, pyusd_key)

        # --- Loan Monitoring (GPU Loans) ---
        all_loans = get_loan_details(client, SUSDAI_ADDR)

        # --- Manual Adjustment for Legacy Loan ---
        # There is one active loan (NVIDIA H200s) originated before the Loan Router deployment.
        # Principal: ~$560k (Remaining Principal from UI: $559,542)
        # We hardcode this to ensure accurate Total Principal tracking.
        legacy_loan_principal = 559_542.00

        # Legacy Loan Expiry Alert
        legacy_loan_expiry = 1848258000  # 2028-07-27

        if legacy_loan_expiry > 0:
            if datetime.datetime.now().timestamp() > legacy_loan_expiry:
                send_alert(
                    Alert(
                        AlertSeverity.MEDIUM,
                        "*Legacy Loan Expired*\n\nThe legacy loan (NVIDIA H200s) has expired.",
                        PROTOCOL,
                    )
                )

        if all_loans or legacy_loan_principal > 0:
            logger.info("--- Active Loan NFTs (Direct Read) ---")
            total_verified_principal = 0

            # Add Legacy Loan
            logger.info("Legacy Loan (H200s): $%s (Hardcoded)", f"{legacy_loan_principal:,.2f}")
            total_verified_principal += legacy_loan_principal

            for loan in all_loans:
                mat_date = datetime.datetime.fromtimestamp(loan["maturity"]).strftime("%Y-%m-%d")
                logger.info("Loan #%04d...: $%s (Mat: %s)", loan["id"] % 10000, f"{loan['principal']:,.2f}", mat_date)
                total_verified_principal += loan["principal"]

            logger.info("Total Verified Principal: $%s", f"{total_verified_principal:,.2f}")

            # Calculate Ratio to Total Supply
            verified_ratio = (total_verified_principal / usdai_supply_fmt * 100) if usdai_supply_fmt > 0 else 0
            logger.info("Verified Loan Ratio: %s%% of Total Supply", f"{verified_ratio:.2f}")

            # --- Alerting on Principal Change ---
            cache_key_principal = f"{PROTOCOL}_verified_principal"
            last_principal = float(get_last_value_for_key_from_file(cache_filename, cache_key_principal))

            diff = abs(total_verified_principal - last_principal)

            # Check for change (allow small dust difference < $1.00 and <1% of total loans)
            percent_change = (diff / last_principal * 100) if last_principal > 0 else 0
            if last_principal != 0 and diff > 1.0 and percent_change >= 1.0:
                change_type = (
                    "increased (New Loan)" if total_verified_principal > last_principal else "reduced (Repayment)"
                )

                msg = (
                    "*sUSDai Loan Activity*\n\n"
                    f"Total Verified Principal has {change_type}.\n"
                    f"Change: ${diff:,.2f} ({percent_change:.2f}% of Total Loans)\n"
                    f"Old Total: ${last_principal:,.2f}\n"
                    f"New Total: ${total_verified_principal:,.2f}\n"
                    f"Current Ratio: {verified_ratio:.2f}% of Supply"
                )
                send_alert(Alert(AlertSeverity.LOW, msg, PROTOCOL))

            # Update cache
            write_last_value_to_file(cache_filename, cache_key_principal, total_verified_principal)

    except Exception as e:
        logger.error("Error: %s", e)
        send_alert(Alert(AlertSeverity.LOW, f"USDai monitoring failed: {e}", PROTOCOL), plain_text=True)


if __name__ == "__main__":
    main()
