from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from utils.telegram import send_telegram_message

PROTOCOL = "ETHENA"

# Ethena transparency API endpoints
SUPPLY_URL = "https://app.ethena.fi/api/solvency/token-supply?symbol=USDe"
COLLATERAL_URL = "https://app.ethena.fi/api/positions/current/collateral?latest=true"
LLAMARISK_URL = "https://api.llamarisk.com/protocols/ethena/overview/all/?format=json"

# Alert thresholds
COLLATERAL_RATIO_TRIGGER = 1.01  # warn

REQUEST_TIMEOUT = 10  # seconds


@dataclass
class ChainMetrics:
    total_usde_supply: float
    total_usde_staked: float
    total_susde_supply: float
    usde_price: float
    susde_price: float


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
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        send_telegram_message(f"❌ {PROTOCOL}: failed to fetch {url}\n{exc}", PROTOCOL)
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
        send_telegram_message(f"⚠️ {PROTOCOL}: supply data is older than 1 day", PROTOCOL, True)
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

    hours_ago = 3
    if is_stale_timestamp(timestamp_collateral, hours_ago):
        send_telegram_message(f"⚠️ Collateral data is older than {hours_ago} hours", PROTOCOL, True)

    if is_stale_timestamp(timestamp_chain, hours_ago):
        send_telegram_message(f"⚠️ Chain data is older than {hours_ago} hours", PROTOCOL, True)

    if is_stale_timestamp(timestamp_reserve, 12):
        send_telegram_message(f"⚠️ Reserve data is older than 12 hours", PROTOCOL, True)

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
    )

    return LlamaRiskData(
        timestamp=timestamp_collateral,
        collateral_value=collateral_sum,
        chain_metrics=cm,
        reserve_fund=reserve_fund_val,
    )


def main():
    supply = get_usde_supply()
    collateral = get_total_collateral_usd()
    llama_risk = get_llamarisk_data()

    if supply is None or collateral is None or llama_risk is None:
        return  # early exit, errors already reported

    if supply == 0:
        send_telegram_message(f"⚠️ USDe: supply reported as 0", PROTOCOL)
        return

    value_diff_trigger = 0.001  # 0.1%
    if abs(supply - llama_risk.chain_metrics.total_usde_supply) / supply > value_diff_trigger:
        send_telegram_message(
            f"⚠️ USDe: supply values are not similar: ethena {supply} != llama_risk {llama_risk.chain_metrics.total_usde_supply}",
            PROTOCOL,
            True,
        )
        return

    if abs(collateral - llama_risk.collateral_value) / collateral > value_diff_trigger:
        send_telegram_message(
            f"⚠️ USDe: collateral values are not similar: ethena {collateral} != llama_risk {llama_risk.collateral_value}",
            PROTOCOL,
            True,
        )
        return

    total_backing_assets = llama_risk.collateral_value + llama_risk.reserve_fund
    ratio = total_backing_assets / supply

    if ratio < COLLATERAL_RATIO_TRIGGER:
        send_telegram_message(
            f"🚨 USDe is almost not fully backed!\nCollateral/Supply ratio = {ratio:.4f}",
            PROTOCOL,
        )

    print(
        f"[{llama_risk.timestamp}] Ethena – collateral: {collateral:,.2f} USD | "
        f"supply: {supply:,.2f} | ratio: {ratio:.4f}"
    )


if __name__ == "__main__":
    main()
