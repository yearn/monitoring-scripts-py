from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from utils.abi import load_abi
from utils.telegram import send_telegram_message
from utils.web3_wrapper import Chain, ChainManager

PROTOCOL = "ETHENA"

# NOTE: ethena cannot be used because it blocked for Github Actions IP
# Ethena transparency API endpoints
SUPPLY_URL = "https://app.ethena.fi/api/solvency/token-supply?symbol=USDe"
COLLATERAL_URL = "https://app.ethena.fi/api/positions/current/collateral?latest=true"
LLAMARISK_URL = "https://api.llamarisk.com/protocols/ethena/overview/all/?format=json"

USDE_ADDRESS = "0x4c9EDD5852cd905f086C759E8383e09bff1E68B3"
SUSDE_ADDRESS = "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"

ABI_ERC20 = load_abi("common-abi/ERC20.json")

# Alert thresholds
COLLATERAL_RATIO_TRIGGER = 1.005  # must be overcollateralized by at least 0.5%

REQUEST_TIMEOUT = 15  # seconds


@dataclass
class ChainMetrics:
    total_usde_supply: float
    total_usde_staked: float
    total_susde_supply: float
    usde_price: float
    susde_price: float
    timestamp: str


@dataclass
class LlamaRiskData:
    timestamp: str
    collateral_value: float
    chain_metrics: ChainMetrics
    reserve_fund: float


def fetch_json(url: str) -> dict | None:
    """Helper that fetches JSON with basic error handling."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code} for {url}")
            print(resp.text)
            return None
        return resp.json()
    except Exception as e:
        print(f"Failed to fetch {url}\n{e}")
        return None


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse various timestamp formats returned by Ethena & LlamaRisk APIs."""
    formats = [
        "%Y-%m-%d %H:%M:%S.%f UTC",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue

    # Fallback to fromisoformat after normalising Z→+00:00
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00").replace(" UTC", ""))
    except Exception:
        return None


def is_stale_timestamp(ts: str, max_age_hours: int = 3) -> bool:
    """Return True if `ts` is older than `max_age_hours`. Un-parsable → considered stale."""
    dt = _parse_timestamp(ts)
    if dt is None:
        return True
    return dt < datetime.utcnow() - timedelta(hours=max_age_hours)


def get_usde_supply() -> float | None:
    """Return total circulating USDe supply in USD terms (raw token amount / 1e18)."""
    data = fetch_json(SUPPLY_URL)
    if not data:
        return None

    timestamp = data.get("timestamp")  # May be missing
    if timestamp and is_stale_timestamp(timestamp):
        print(f"⚠️ Data from ethena is old: {timestamp}")
        return None

    return float(data["supply"]) / 1e18


def get_total_collateral_usd() -> float | None:
    """Return USD value of all collateral backing USDe."""
    data = fetch_json(COLLATERAL_URL)
    if not data:
        return None

    return float(data["totalBackingAssetsInUsd"])


def get_llamarisk_data() -> LlamaRiskData | None:
    """Return data from LlamaRisk API."""
    data = fetch_json(LLAMARISK_URL)
    if not data:
        return None

    collateral_metrics = data["collateral_metrics"]
    chain_metrics_raw = data["chain_metrics"]
    reserve_fund = data["reserve_fund_metrics"]

    timestamp_collateral = collateral_metrics["latest"]["timestamp"]
    timestamp_chain = chain_metrics_raw["latest"]["timestamp"]
    timestamp_reserve = reserve_fund["latest"]["timestamp"]

    hours_ago = 12
    if is_stale_timestamp(timestamp_collateral, hours_ago):
        send_telegram_message(
            f"⚠️ Collateral data is older than {hours_ago} hours. Timestamp: {timestamp_collateral}", PROTOCOL, True
        )

    if is_stale_timestamp(timestamp_chain, hours_ago):
        # NOTE: don't send telegram message because there is a problem with the API
        print(f"⚠️ Chain data is older than {hours_ago} hours. Timestamp: {timestamp_chain}")

    if is_stale_timestamp(timestamp_reserve, hours_ago):
        send_telegram_message(
            f"⚠️ Reserve data is older than {hours_ago} hours. Timestamp: {timestamp_reserve}", PROTOCOL, True
        )

    # sum all collateral values
    collateral_metrics = collateral_metrics["latest"]["data"]["collateral"]
    collateral_sum = sum(item["usdAmount"] for item in collateral_metrics)

    chain_metrics_data = chain_metrics_raw["latest"]["data"]
    reserve_fund_val = float(reserve_fund["latest"]["data"]["value"])

    # Build ChainMetrics dataclass with safe conversions
    def _to_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    cm = ChainMetrics(
        total_usde_supply=_to_float(chain_metrics_data.get("totalUsdeSupply", 0)) / 1e18,
        total_usde_staked=_to_float(chain_metrics_data.get("totalUsdeStaked", 0)) / 1e18,
        total_susde_supply=_to_float(chain_metrics_data.get("totalSusdeSupply", 0)) / 1e18,
        usde_price=_to_float(chain_metrics_data.get("usdePrice", 1)),
        susde_price=_to_float(chain_metrics_data.get("susdePrice", 1)),
        timestamp=timestamp_chain,
    )

    return LlamaRiskData(
        timestamp=timestamp_collateral,
        collateral_value=collateral_sum,
        chain_metrics=cm,
        reserve_fund=reserve_fund_val,
    )


def get_tokens_supply() -> tuple[float, float] | tuple[None, None]:
    client = ChainManager.get_client(Chain.MAINNET)

    try:
        usde = client.eth.contract(address=USDE_ADDRESS, abi=ABI_ERC20)
        susde = client.eth.contract(address=SUSDE_ADDRESS, abi=ABI_ERC20)
    except Exception as e:
        error_message = f"Error creating contract instances: {e}. Check ABI paths and contract addresses."
        print(error_message)
        return  # Cannot proceed without contracts

    usde_supply = None
    susde_supply = None
    # --- Combined Blockchain Calls ---
    try:
        with client.batch_requests() as batch:
            batch.add(usde.functions.totalSupply())
            batch.add(susde.functions.totalSupply())

            responses = client.execute_batch(batch)

            if len(responses) == 2:
                usde_supply, susde_supply = responses
                print(f"Raw Data - USDe Supply: {usde_supply}, Susde Supply: {susde_supply}")
            else:
                raise Exception(f"Batch Call: Expected 3 responses, got {len(responses)}")

    except Exception:
        send_telegram_message("Error during batch blockchain calls", PROTOCOL)
        return None, None  # Cannot proceed if batch fails

    return usde_supply, susde_supply


def main():
    llama_risk = get_llamarisk_data()

    if llama_risk is None:
        send_telegram_message("⚠️ Failed to fetch data", PROTOCOL, True)
        return

    # NOTE: ethena data is not available, so we use llama_risk data only
    # supply = get_usde_supply()
    # collateral = get_total_collateral_usd()
    supply = llama_risk.chain_metrics.total_usde_supply
    collateral = llama_risk.collateral_value
    value_diff_trigger = 0.001  # 0.1%
    if abs(supply - llama_risk.chain_metrics.total_usde_supply) / supply > value_diff_trigger:
        send_telegram_message(
            f"⚠️ USDe: supply values are not similar: ethena {supply} != llama_risk {llama_risk.chain_metrics.total_usde_supply}",
            PROTOCOL,
        )
        return

    if abs(collateral - llama_risk.collateral_value) / collateral > value_diff_trigger:
        send_telegram_message(
            f"⚠️ USDe: collateral values are not similar: ethena {collateral} != llama_risk {llama_risk.collateral_value}",
            PROTOCOL,
        )
        return

    # NOTE: don't check on-chain data if llama_risk data is old because it will be out of sync
    parsed_timestamp = _parse_timestamp(llama_risk.chain_metrics.timestamp)
    llama_risk_is_old = parsed_timestamp is None or datetime.now() - parsed_timestamp > timedelta(hours=3)
    total_backing_assets = llama_risk.collateral_value + llama_risk.reserve_fund

    if llama_risk_is_old:
        # NOTE: skip validating old data, we already got telegram message
        print(f"LlamaRisk data is old: {llama_risk.timestamp}")
        return

    ratio = total_backing_assets / supply

    if ratio < COLLATERAL_RATIO_TRIGGER:
        send_telegram_message(
            f"🚨 USDe is almost not fully backed!\nCollateral/Supply ratio = {ratio:.4f}. \nLlamaRisk timestamp: {llama_risk.timestamp}",
            PROTOCOL,
            True,
        )
    if ratio < 1:
        send_telegram_message(
            f"🚨 USDe is not fully backed!\nCollateral/Supply ratio = {ratio:.4f}. \nLlamaRisk timestamp: {llama_risk.timestamp}",
            PROTOCOL,
        )

    # Validate LlamaRisk data with on-chain data
    usde_supply, susde_supply = get_tokens_supply()
    # remove decimasl because llama risk values are without it
    usde_supply = usde_supply / 1e18
    susde_supply = susde_supply / 1e18
    # NOTE: set higher value_diff_trigger because on-chain and off-chain values are not in sync
    value_diff_trigger = 0.005  # 0.5%

    error_messages = []

    if abs(usde_supply - supply) / supply > value_diff_trigger:
        error_messages.append(
            "USDe supply values are not similar onchain diffrent from LlamaRisk: "
            f"{supply} != {usde_supply} (diff: {abs(usde_supply - supply) / supply})"
        )

    if abs(susde_supply - llama_risk.chain_metrics.total_susde_supply) / susde_supply > value_diff_trigger:
        error_messages.append(
            "sUSDe supply values are not similar onchain diffrent from LlamaRisk: "
            f"{susde_supply} != {llama_risk.chain_metrics.total_susde_supply} "
            f"(diff: {abs(susde_supply - llama_risk.chain_metrics.total_susde_supply) / susde_supply})"
        )

    if error_messages:
        message = "⚠️ " + "\n".join(error_messages)
        send_telegram_message(message, PROTOCOL)

    print(
        f"[{llama_risk.timestamp}] Ethena – collateral: {collateral:,.2f} USD | "
        f"supply: {supply:,.2f} | ratio: {ratio:.4f}\n"
        f"onchain data: usde supply = {usde_supply / 1e18:,.2f} | susde supply = {susde_supply / 1e18:,.2f}"
    )


if __name__ == "__main__":
    main()
