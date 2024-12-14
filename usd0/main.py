import os, json
from web3 import Web3
from dotenv import load_dotenv
from dune_client.client import DuneClient
from utils.telegram import send_telegram_message

load_dotenv()
dune = DuneClient(os.getenv("DUNE_API_KEY"))
PROTOCOL = "USD0"
COLLATERAL_FACTOR_MINIMUM = 100.6

peg_threshold = 0.001  # 0.1% used
provider_url = os.getenv("PROVIDER_URL_MAINNET")
w3 = Web3(Web3.HTTPProvider(provider_url))

with open("common-abi/CurvePool.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_curve_pool = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_curve_pool = abi_data

curve_pool = w3.eth.contract(
    address="0x14100f81e33C33Ecc7CDac70181Fb45B6E78569F", abi=abi_curve_pool
)


def check_usd0_crv_pool_rate(amount_in):
    try:
        swap_res = curve_pool.functions.get_dy(
            0, 1, int(amount_in)
        ).call()  # swap from usd0 to usdc
        return swap_res  # return result is in 6 decimals
    except Exception as e:
        error_message = f"Error calling get_dy in curve pool: {e}"
        send_telegram_message(error_message, PROTOCOL)


def check_peg(usdc_rate, curve_rate):
    if curve_rate == 0:
        return False
    # Calculate the percentage difference
    difference = abs(usdc_rate - curve_rate)
    percentage_diff = difference / usdc_rate
    return percentage_diff >= peg_threshold  # 0.06 >= 0.05


def check_peg_usd0():
    amounts = [1e18, 1000_000e18, 10_000_000e18]
    message = ""
    for amount in amounts:
        curve_rate = check_usd0_crv_pool_rate(amount)  # in 6 decimals
        if curve_rate is not None and check_peg(amount / 1e12, curve_rate):
            human_readable_amount = amount / 1e18
            human_readable_result = curve_rate / 1e6
            message += f"📊 Swap result for amount {human_readable_amount:.2f}: {human_readable_result:.2f}"
            send_telegram_message(message, PROTOCOL)


def query_cf():
    query_result = dune.get_latest_result(3886520)
    newest_data = query_result.result.rows[0]
    collateral_factor = newest_data["collateral_factor"]
    if collateral_factor < COLLATERAL_FACTOR_MINIMUM:
        # Collateral factor has fallen below accept risk
        message = f"USD0 collateral factor is {collateral_factor}"
        send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    query_cf()
    check_peg_usd0()
