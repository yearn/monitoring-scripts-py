import time
from dataclasses import dataclass
from datetime import datetime

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
SDOLA_CONTRACT = "0xb45ad160634c528Cc3D2926d9807104FA3157305"
SDOLA_ABI = load_abi("inverse/abi/sdola.json")

@dataclass
class FedOverview:
    circSupply: float
    protocol: str
    name: str
    projectImage: str
    supply: float
    tvl: float
    borrows: float

@dataclass
class Dolastaking:
    dola_price_usd: float
    tvl_usd: float
    total_assets: float
    total_assets30d: float
    total_assets90d: float
    s_dola_ex_rate: float
    s_dola_supply: float
    s_dola_total_assets: float


def is_timestamp_recent(timestamp_ms: int, max_age_hours: int = 2) -> bool:
    current_time_ms = int(time.time() * 1000)
    max_age_ms = max_age_hours * 60 * 60 * 1000
    return (current_time_ms - timestamp_ms) <= max_age_ms


def get_fed_overview() -> FedOverview:
    session = create_session_with_retry()
    response = session.get(FED_OVERVIEW_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to get fed overview: {response.status_code}")

    timestamp = response.json()["timestamp"]
    if not is_timestamp_recent(timestamp):
        raise Exception(f"Data is too old. Timestamp: {datetime.fromtimestamp(timestamp/1000)}")

    feds_overview = response.json()["fedOverviews"]
    firm = feds_overview[0]
    if firm["protocol"] != "FiRM":
        raise Exception("FiRM is not the first protocol in the list")
    return FedOverview(
        circSupply=firm["circSupply"],
        protocol=firm["protocol"],
        name=firm["name"],
        projectImage=firm["projectImage"],
        supply=firm["supply"],
        tvl=firm["tvl"],
        borrows=firm["borrows"]
    )

def get_dola_circulating_supply():
    response = requests.get(DOLA_CIRCULATING_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to get dola circulating supply: {response.status_code}")
    return response.json()

def create_session_with_retry(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 504)
) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_dola_staking() -> Dolastaking:
    session = create_session_with_retry()
    try:
        response = session.get(DOLA_STAKING_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        timestamp = data["timestamp"]
        if not is_timestamp_recent(timestamp):
            raise Exception(f"Data is too old. Timestamp: {datetime.fromtimestamp(timestamp/1000)}")

        return Dolastaking(
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

def get_sdola_supply() -> int:
    client = ChainManager.get_client(Chain.MAINNET)
    contract = client.eth.contract(address=SDOLA_CONTRACT, abi=SDOLA_ABI)
    return contract.functions.totalSupply().call()

if __name__ == "__main__":
    fed_overview = get_fed_overview()
    dola_circulating_supply = get_dola_circulating_supply()
    # NOTE: there is a 9M DOLA from frontier(bad debt) and gearbox
    if fed_overview.circSupply > dola_circulating_supply + 9e6:
        send_telegram_message(f"🚨 FiRM has {fed_overview.circSupply - dola_circulating_supply - 9e6} more DOLA than the circulating supply", PROTOCOL_NAME)

    if fed_overview.tvl * 0.8 < fed_overview.borrows:
        send_telegram_message(f"🚨 Borrows exceed 80% of the TVL. FiRM has TVL: {fed_overview.tvl} and borrows: {fed_overview.borrows}.", PROTOCOL_NAME)

    # other metrics like liquidity should be handled in liquidity repository

    dola_staking = get_dola_staking()
    if dola_staking.dola_price_usd < 0.998:
        send_telegram_message(f"🚨 DOLA price is below $0.998. DOLA price: {dola_staking.dola_price_usd}", PROTOCOL_NAME)

    if dola_staking.s_dola_total_assets < dola_staking.s_dola_supply:
        send_telegram_message(f"🚨 DOLA staking is not enough. DOLA staking: {dola_staking.s_dola_total_assets} and DOLA supply: {dola_staking.s_dola_supply}", PROTOCOL_NAME)

    ex_rate = dola_staking.s_dola_total_assets / dola_staking.s_dola_supply
    if ex_rate != dola_staking.s_dola_ex_rate:
        send_telegram_message(f"🚨 DOLA ex rate is not correct, calculated: {ex_rate} and target: {dola_staking.s_dola_ex_rate}", PROTOCOL_NAME)

    # Verify backend is returning correct supply
    sdola_supply = get_sdola_supply() / 1e18
    if sdola_supply < dola_staking.s_dola_supply * 0.99 or sdola_supply > dola_staking.s_dola_supply * 1.01:
        send_telegram_message(f"🚨 SDOLA supply is not correct, calculated: {sdola_supply} and target: {dola_staking.s_dola_supply}", PROTOCOL_NAME)
