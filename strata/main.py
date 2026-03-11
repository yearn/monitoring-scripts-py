import requests
from web3 import Web3

from utils.abi import load_abi
from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.logging import get_logger
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL = "strata"
logger = get_logger(PROTOCOL)

SRUSDE = Web3.to_checksum_address("0x3d7d6fdf07EE548B939A80edbc9B2256d0cdc003")
JRUSDE = Web3.to_checksum_address("0xC58D044404d8B14e953C115E67823784dEA53d8F")
USDE_COIN_KEY = "ethereum:0x4c9edd5852cd905f086c759e8383e09bff1e68b3"

WEI = 10**18
REQUEST_TIMEOUT = 15

# Core thresholds
JR_TO_SR_WARNING_MIN = 0.10
JR_TO_SR_CRITICAL_MIN = 0.05
JR_ASSETS_DROP_ALERT_RATIO = 0.15
JR_RATE_DROP_ALERT_RATIO = 0.02
USDE_PEG_WARNING = 0.005
USDE_PEG_CRITICAL = 0.02

ERC4626_ABI = load_abi("common-abi/YearnV3Vault.json")


def _cache_float(key: str) -> float | None:
    value = get_last_value_for_key_from_file(cache_filename, key)
    if value == 0:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _set_cache_float(key: str, value: float) -> None:
    write_last_value_to_file(cache_filename, key, value)


def _breach_once(cache_key: str, condition: bool, message: str, messages: list[str]) -> None:
    raw_state = get_last_value_for_key_from_file(cache_filename, cache_key)
    state = int(float(raw_state)) if raw_state != 0 else 0

    if condition:
        if state == 0:
            messages.append(message)
        write_last_value_to_file(cache_filename, cache_key, 1)
    elif state == 1:
        write_last_value_to_file(cache_filename, cache_key, 0)


def _fetch_usde_price() -> float | None:
    url = f"https://coins.llama.fi/prices/current/{USDE_COIN_KEY}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning("USDe price fetch failed: HTTP %s", response.status_code)
            return None

        data = response.json()
        return float(data["coins"][USDE_COIN_KEY]["price"])
    except Exception as e:
        logger.warning("USDe price fetch failed: %s", e)
        return None


def main() -> None:
    client = ChainManager.get_client(Chain.MAINNET)

    sr = client.get_contract(SRUSDE, ERC4626_ABI)
    jr = client.get_contract(JRUSDE, ERC4626_ABI)

    try:
        with client.batch_requests() as batch:
            batch.add(sr.functions.totalAssets())
            batch.add(sr.functions.totalSupply())
            batch.add(sr.functions.convertToAssets(WEI))
            batch.add(jr.functions.totalAssets())
            batch.add(jr.functions.totalSupply())
            batch.add(jr.functions.convertToAssets(WEI))

            responses = client.execute_batch(batch)

        if len(responses) != 6:
            raise ValueError(f"Batch call expected 6 responses, got {len(responses)}")

        sr_total_assets, sr_total_supply, sr_rate_raw, jr_total_assets, jr_total_supply, jr_rate_raw = responses

        sr_assets = float(sr_total_assets) / WEI
        jr_assets = float(jr_total_assets) / WEI
        sr_supply = float(sr_total_supply) / WEI
        jr_supply = float(jr_total_supply) / WEI
        sr_rate = float(sr_rate_raw) / WEI
        jr_rate = float(jr_rate_raw) / WEI

        jr_to_sr_ratio = (jr_assets / sr_assets) if sr_assets > 0 else 0.0
        coverage_ratio = 1.0 + jr_to_sr_ratio

        logger.info(
            "sr_assets=%s sr_supply=%s sr_rate=%s jr_assets=%s jr_supply=%s jr_rate=%s jr_to_sr_ratio=%s coverage_ratio=%s",
            f"{sr_assets:,.2f}",
            f"{sr_supply:,.2f}",
            f"{sr_rate:.6f}",
            f"{jr_assets:,.2f}",
            f"{jr_supply:,.2f}",
            f"{jr_rate:.6f}",
            f"{jr_to_sr_ratio:.4%}",
            f"{coverage_ratio:.4f}",
        )

        messages: list[str] = []

        if sr_assets <= 0:
            messages.append("🚨 Strata srUSDe totalAssets is zero or invalid.")

        # Coverage guardrail proxy: coverage ~= 1 + (jr_assets / sr_assets)
        _breach_once(
            f"{PROTOCOL}_coverage_critical",
            jr_to_sr_ratio < JR_TO_SR_CRITICAL_MIN,
            (
                "🚨 Strata junior buffer is critically low.\n"
                f"jr/sr ratio: {jr_to_sr_ratio:.2%} (critical < {JR_TO_SR_CRITICAL_MIN:.0%}).\n"
                f"Implied coverage ratio: {coverage_ratio:.4f}"
            ),
            messages,
        )
        _breach_once(
            f"{PROTOCOL}_coverage_warning",
            JR_TO_SR_CRITICAL_MIN <= jr_to_sr_ratio < JR_TO_SR_WARNING_MIN,
            (
                "⚠️ Strata junior buffer is getting thin.\n"
                f"jr/sr ratio: {jr_to_sr_ratio:.2%} (warning < {JR_TO_SR_WARNING_MIN:.0%}).\n"
                f"Implied coverage ratio: {coverage_ratio:.4f}"
            ),
            messages,
        )

        # srUSDe share value should not decrease.
        sr_rate_cache_key = f"{PROTOCOL}_sr_rate"
        prev_sr_rate = _cache_float(sr_rate_cache_key)
        if prev_sr_rate is not None and sr_rate < prev_sr_rate:
            drop_bps = ((prev_sr_rate - sr_rate) / prev_sr_rate) * 10_000
            messages.append(
                "🚨 srUSDe share value decreased.\n"
                f"previous: {prev_sr_rate:.8f} current: {sr_rate:.8f} ({drop_bps:.2f} bps drop)"
            )
        _set_cache_float(sr_rate_cache_key, sr_rate)

        # jrUSDe drawdowns are expected in stress, but big drops should alert.
        jr_rate_cache_key = f"{PROTOCOL}_jr_rate"
        prev_jr_rate = _cache_float(jr_rate_cache_key)
        if prev_jr_rate is not None and prev_jr_rate > 0:
            jr_rate_change = (jr_rate - prev_jr_rate) / prev_jr_rate
            if jr_rate_change <= -JR_RATE_DROP_ALERT_RATIO:
                messages.append(
                    "⚠️ jrUSDe share value dropped quickly.\n"
                    f"previous: {prev_jr_rate:.8f} current: {jr_rate:.8f} ({jr_rate_change:.2%})"
                )
        _set_cache_float(jr_rate_cache_key, jr_rate)

        jr_assets_cache_key = f"{PROTOCOL}_jr_assets"
        prev_jr_assets = _cache_float(jr_assets_cache_key)
        if prev_jr_assets is not None and prev_jr_assets > 0:
            jr_assets_change = (jr_assets - prev_jr_assets) / prev_jr_assets
            if jr_assets_change <= -JR_ASSETS_DROP_ALERT_RATIO:
                messages.append(
                    "⚠️ jrUSDe TVL dropped quickly.\n"
                    f"previous: ${prev_jr_assets:,.2f} current: ${jr_assets:,.2f} ({jr_assets_change:.2%})"
                )
        _set_cache_float(jr_assets_cache_key, jr_assets)

        usde_price = _fetch_usde_price()
        if usde_price is not None:
            usde_deviation = abs(usde_price - 1.0)
            _breach_once(
                f"{PROTOCOL}_usde_peg_critical",
                usde_deviation >= USDE_PEG_CRITICAL,
                (f"🚨 USDe peg is heavily off $1.\nprice: ${usde_price:.4f}, deviation: {usde_deviation:.2%}"),
                messages,
            )
            _breach_once(
                f"{PROTOCOL}_usde_peg_warning",
                USDE_PEG_WARNING <= usde_deviation < USDE_PEG_CRITICAL,
                (f"⚠️ USDe peg moved away from $1.\nprice: ${usde_price:.4f}, deviation: {usde_deviation:.2%}"),
                messages,
            )

        if messages:
            send_telegram_message("\n\n".join(messages), PROTOCOL)

    except Exception as e:
        logger.error("Error: %s", e)
        send_telegram_message(f"⚠️ Strata monitoring failed: {e}", PROTOCOL, False, True)


if __name__ == "__main__":
    main()
