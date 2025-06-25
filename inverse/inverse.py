import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.abi import load_abi
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

PROTOCOL_NAME = "INVERSE"
INVERSE_API_URL = "https://www.inverse.finance/api"
FED_OVERVIEW_URL = INVERSE_API_URL + "/transparency/fed-overview"
DOLA_CIRCULATING_URL = INVERSE_API_URL + "/dola/circulating-supply"
DOLA_STAKING_URL = INVERSE_API_URL + "/dola-staking"
GOVERNANCE_URL = INVERSE_API_URL + "/governance-notifs"
DOLA_CONTRACT = "0x865377367054516e17014CcdED1e7d814EDC9ce4"
SDOLA_CONTRACT = "0xb45ad160634c528Cc3D2926d9807104FA3157305"
ERC20_ABI = load_abi("common-abi/ERC20.json")


class FedType(Enum):
    FIRM = "FiRM"
    AMM = "AMM"
    CROSS_CHAIN = "CROSS_CHAIN"
    DEPRECATED = "DEPRECATED"


@dataclass
class FedInfo:
    circSupply: float
    protocol: str
    name: str
    supply: float
    tvl: float
    borrows: float
    fed_type: FedType
    utilization_ratio: Optional[float] = None
    lp_total_supply: Optional[float] = None
    lp_price: Optional[float] = None


@dataclass
class DolaStaking:
    dola_price_usd: float
    tvl_usd: float
    total_assets: float
    total_assets30d: float
    total_assets90d: float
    s_dola_ex_rate: float
    s_dola_supply: float
    s_dola_total_assets: float


@dataclass
class FedMonitoringMetrics:
    total_fed_supply: float
    firm_utilization: float
    amm_feds_backing: Dict[str, float]
    peg_deviation: float


def is_timestamp_recent(timestamp_ms: int, max_age_hours: int = 2) -> bool:
    current_time_ms = int(time.time() * 1000)
    max_age_ms = max_age_hours * 60 * 60 * 1000
    return (current_time_ms - timestamp_ms) <= max_age_ms


def classify_fed_type(protocol: str) -> FedType:
    """Classify Fed type based on protocol and name"""
    if protocol == "FiRM":
        return FedType.FIRM
    elif protocol in ["Frontier", "Fuse6", "Fuse24"]:
        return FedType.DEPRECATED
    elif protocol in ["Badger", "0xb1", "Yearn", "Convex", "Scream", "Velo", "Aura", "AuraEuler", "Aero", "FraxPyusd"]:
        return FedType.AMM
    elif protocol in ["ArbiFed", "BaseCCTP", "OptiCCTP", "Gearbox"]:
        return FedType.CROSS_CHAIN
    else:
        return FedType.AMM  # Default to AMM for unknown protocols


def get_all_feds_overview() -> List[FedInfo]:
    """Get comprehensive overview of all Fed contracts"""
    session = create_session_with_retry()
    response = session.get(FED_OVERVIEW_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to get fed overview: {response.status_code}")

    data = response.json()
    timestamp = data["timestamp"]
    if not is_timestamp_recent(timestamp):
        raise Exception(f"Data is too old. Timestamp: {datetime.fromtimestamp(timestamp / 1000)}")

    feds_overview = data["fedOverviews"]
    feds = []

    for fed_data in feds_overview:
        fed_type = classify_fed_type(fed_data["protocol"])

        # Safely get values with defaults for missing fields
        tvl = fed_data.get("tvl", 0.0)
        supply = fed_data.get("supply", 0.0)
        borrows = fed_data.get("borrows", 0.0)
        circ_supply = fed_data.get("circSupply", 0.0)

        utilization_ratio = None
        if fed_type == FedType.FIRM and tvl > 0:
            utilization_ratio = borrows / tvl

        fed_info = FedInfo(
            circSupply=circ_supply,
            protocol=fed_data["protocol"],
            name=fed_data["name"],
            supply=supply,
            tvl=tvl,
            borrows=borrows,
            fed_type=fed_type,
            utilization_ratio=utilization_ratio,
            lp_total_supply=fed_data.get("lpTotalSupply", None),
            lp_price=fed_data.get("lpPrice", None),
        )
        feds.append(fed_info)

    return feds


def get_dola_circulating_supply() -> float:
    response = requests.get(DOLA_CIRCULATING_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to get dola circulating supply: {response.status_code}")
    return response.json()


def create_session_with_retry(
    retries: int = 3, backoff_factor: float = 0.5, status_forcelist: tuple = (500, 502, 504)
) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_dola_staking() -> DolaStaking:
    session = create_session_with_retry()
    try:
        response = session.get(DOLA_STAKING_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        timestamp = data["timestamp"]
        if not is_timestamp_recent(timestamp):
            raise Exception(f"Data is too old. Timestamp: {datetime.fromtimestamp(timestamp / 1000)}")

        return DolaStaking(
            dola_price_usd=data["dolaPriceUsd"],
            tvl_usd=data["tvlUsd"],
            total_assets=data["totalAssets"],
            total_assets30d=data["totalAssets30d"],
            total_assets90d=data["totalAssets90d"],
            s_dola_ex_rate=data["sDolaExRate"],
            s_dola_supply=data["sDolaSupply"],
            s_dola_total_assets=data["sDolaTotalAssets"],
        )
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get dola staking after retries: {str(e)}")
    finally:
        session.close()


def get_tokens_supply() -> tuple[float, float]:
    client = ChainManager.get_client(Chain.MAINNET)
    dola_contract = client.eth.contract(address=DOLA_CONTRACT, abi=ERC20_ABI)
    sdola_contract = client.eth.contract(address=SDOLA_CONTRACT, abi=ERC20_ABI)

    with client.batch_requests() as batch:
        batch.add(dola_contract.functions.totalSupply())
        batch.add(sdola_contract.functions.totalSupply())
        responses = client.execute_batch(batch)
        if len(responses) == 2:
            dola_supply, sdola_supply = responses
            return dola_supply / 1e18, sdola_supply / 1e18
        else:
            raise Exception(f"Expected 2 responses, got {len(responses)} from blockchain batch call")


def calculate_fed_metrics(feds: List[FedInfo], dola_price: float) -> FedMonitoringMetrics:
    """Calculate comprehensive Fed monitoring metrics"""
    total_fed_supply = sum(fed.supply for fed in feds)

    # FiRM utilization
    firm_feds = [fed for fed in feds if fed.fed_type == FedType.FIRM]
    firm_utilization = 0.0
    if firm_feds:
        firm_fed = firm_feds[0]  # Should only be one FiRM Fed
        firm_utilization = firm_fed.utilization_ratio or 0.0

    # AMM Feds backing ratios
    amm_feds_backing = {}
    for fed in feds:
        if fed.fed_type == FedType.AMM and fed.lp_total_supply is not None:
            amm_feds_backing[fed.protocol] = fed.lp_total_supply * fed.lp_price

    # Peg stability score (based on DOLA price deviation from $1)
    peg_deviation = abs(1.0 - dola_price)

    return FedMonitoringMetrics(
        total_fed_supply=total_fed_supply,
        firm_utilization=firm_utilization,
        amm_feds_backing=amm_feds_backing,
        peg_deviation=peg_deviation,
    )


def monitor_firm_fed(fed: FedInfo) -> None:
    """Monitor FiRM Fed for risk conditions"""
    if fed.fed_type != FedType.FIRM:
        return

    # High utilization alert
    if fed.utilization_ratio and fed.utilization_ratio > 0.8:
        send_telegram_message(
            f"🚨 FiRM utilization is high: {fed.utilization_ratio:.1%}. "
            f"TVL: ${fed.tvl:,.0f}, Borrows: ${fed.borrows:,.0f}",
            PROTOCOL_NAME,
        )

    # Collateralization concerns
    if fed.supply > 0 and fed.borrows > 0:
        collateralization_ratio = fed.supply / fed.borrows
        if collateralization_ratio < 1.2:
            send_telegram_message(
                f"🚨 FiRM collateralization is low: {collateralization_ratio:.1%}. "
                f"Supply: ${fed.supply:,.0f}, Borrows: ${fed.borrows:,.0f}",
                PROTOCOL_NAME,
            )
    else:
        send_telegram_message("Missing supply or borrows for FiRM Fed", PROTOCOL_NAME)


def monitor_overall_risk(metrics: FedMonitoringMetrics, dola_price: float, dola_supply: float) -> None:
    """Monitor overall system risk"""
    if metrics.firm_utilization > 0.8:
        send_telegram_message(
            f"🚨 FiRM utilization is high: {metrics.firm_utilization:.1%}. "
            f"TVL: ${metrics.total_fed_supply:,.0f}, Borrows: ${metrics.total_fed_supply:,.0f}",
            PROTOCOL_NAME,
        )
    # DOLA price alerts
    if metrics.peg_deviation > 0.005:
        send_telegram_message(
            f"🚨 DOLA peg deviation: {metrics.peg_deviation:.4f}. DOLA price: ${dola_price:.4f}", PROTOCOL_NAME
        )
    # DOLA supply alerts
    if abs(dola_supply - metrics.total_fed_supply) / dola_supply > 0.005:
        send_telegram_message(
            f"🚨 DOLA supply mismatch: On-chain {dola_supply:,.0f} "
            f"vs API {metrics.total_fed_supply:,.0f} ({abs(dola_supply - metrics.total_fed_supply) / dola_supply:.1%} diff)",
            PROTOCOL_NAME,
        )


def monitor_deprecated_feds(feds: List[FedInfo]) -> None:
    """Monitor deprecated Feds for unexpected activity"""
    deprecated_feds = [fed for fed in feds if fed.fed_type == FedType.DEPRECATED]

    for fed in deprecated_feds:
        if fed.protocol == "Frontier":
            if fed.supply > 19450000:
                send_telegram_message(
                    f"⚠️ Frontier Fed has significant supply: ${fed.supply:,.0f}. Above the last recorded value.",
                    PROTOCOL_NAME,
                )
        elif fed.supply > 1000:
            send_telegram_message(
                f"⚠️ Deprecated {fed.protocol} Fed has significant supply: ${fed.supply:,.0f}. Above the last recorded value.",
                PROTOCOL_NAME,
            )


def monitor_total_fed_supply_borrows(feds: List[FedInfo]) -> None:
    """Monitor total Fed supply for unexpected activity"""
    total_fed_supply = sum(fed.supply for fed in feds)
    total_fed_borrows = sum(fed.borrows for fed in feds)
    if total_fed_borrows > total_fed_supply * 0.8:
        send_telegram_message(
            f"🚨 Total Fed borrows is greater than supply: ${total_fed_borrows:,.0f} > ${total_fed_supply:,.0f} * 0.8",
            PROTOCOL_NAME,
        )


def monitor_dola_staking(dola_staking: DolaStaking, sdola_supply_onchain: float) -> None:
    """Monitor DOLA staking for unexpected activity"""
    # DOLA Staking monitoring (existing logic)
    if dola_staking.s_dola_total_assets < dola_staking.s_dola_supply:
        send_telegram_message(
            f"🚨 sDOLA undercollateralized: Assets {dola_staking.s_dola_total_assets:,.0f} "
            f"< Supply {dola_staking.s_dola_supply:,.0f}",
            PROTOCOL_NAME,
        )

    # Exchange rate validation
    calculated_ex_rate = dola_staking.s_dola_total_assets / dola_staking.s_dola_supply
    if abs(calculated_ex_rate - dola_staking.s_dola_ex_rate) > 0.001:
        send_telegram_message(
            f"🚨 sDOLA exchange rate mismatch: Calculated {calculated_ex_rate:.4f} "
            f"vs API {dola_staking.s_dola_ex_rate:.4f}",
            PROTOCOL_NAME,
        )
    # sDOLA supply verification
    supply_diff_pct = abs(sdola_supply_onchain - dola_staking.s_dola_supply) / dola_staking.s_dola_supply
    if supply_diff_pct > 0.01:  # 1% tolerance
        send_telegram_message(
            f"🚨 sDOLA supply mismatch: On-chain {sdola_supply_onchain:,.0f} "
            f"vs API {dola_staking.s_dola_supply:,.0f} ({supply_diff_pct:.1%} diff)",
            PROTOCOL_NAME,
        )


if __name__ == "__main__":
    try:
        # Get all Fed data
        feds = get_all_feds_overview()
        dola_staking = get_dola_staking()
        metrics = calculate_fed_metrics(feds, dola_staking.dola_price_usd)

        # Monitor each Fed type
        for fed in feds:
            if fed.fed_type == FedType.FIRM:
                monitor_firm_fed(fed)

        # Monitor overall risk
        dola_supply, sdola_supply = get_tokens_supply()
        monitor_overall_risk(metrics, dola_staking.dola_price_usd, dola_supply)
        monitor_deprecated_feds(feds)
        monitor_total_fed_supply_borrows(feds)
        monitor_dola_staking(dola_staking, sdola_supply)
        print(f"✅ Monitoring completed successfully. Checked {len(feds)} Feds.")

    except Exception as e:
        print(f"❌ Error during monitoring: {str(e)}")
        send_telegram_message(f"🚨 Inverse monitoring error: {str(e)}", PROTOCOL_NAME)
