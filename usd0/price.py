import os, json
from web3 import Web3
from dotenv import load_dotenv
from utils.telegram import send_telegram_message

load_dotenv()
PROTOCOL = "USD0"

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

    # Create batch request
    with w3.batch_requests() as batch:
        # Add all curve pool requests to the batch
        for amount in amounts:
            batch.add(curve_pool.functions.get_dy(0, 1, int(amount)))

        # Execute all at once
        try:
            curve_rates = batch.execute()
            if len(curve_rates) != len(amounts):
                error_message = f"Batch response length mismatch. Expected: {len(amounts)}, Got: {len(curve_rates)}"
                send_telegram_message(error_message, PROTOCOL)
                return
        except Exception as e:
            error_message = f"Error executing batch curve pool calls: {e}"
            send_telegram_message(error_message, PROTOCOL)
            return

    # Process results outside the batch
    for amount, curve_rate in zip(amounts, curve_rates):
        if curve_rate is not None and check_peg(amount / 1e12, curve_rate):
            human_readable_amount = amount / 1e18
            human_readable_result = curve_rate / 1e6
            message += f"📊 Swap result for amount {human_readable_amount:.2f}: {human_readable_result:.2f}"
            send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    check_peg_usd0()
