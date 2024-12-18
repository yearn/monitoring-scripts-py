from web3 import Web3
from dotenv import load_dotenv
import os, json
from utils.telegram import send_telegram_message

load_dotenv()

PROTOCOL = "LIDO"
peg_threshold = 0.05  # 5% used
provider_url = os.getenv("PROVIDER_URL_MAINNET")
w3 = Web3(Web3.HTTPProvider(provider_url))

with open("lido/steth/abi/CurvePool.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_curve_pool = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_curve_pool = abi_data

with open("lido/steth/abi/Steth.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_steth = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_steth = abi_data


steth = w3.eth.contract(
    address="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", abi=abi_steth
)
curve_pool = w3.eth.contract(
    address="0xDC24316b9AE028F1497c275EB9192a3Ea0f67022", abi=abi_curve_pool
)


def check_steth_validator_rate():
    # Use batch requests
    with w3.batch_requests() as batch:
        # Add calls to the batch
        batch.add(steth.functions.totalSupply())
        batch.add(steth.functions.getTotalPooledEther())

        # Execute all calls at once
        responses = batch.execute()

        if len(responses) != 2:
            raise ValueError(f"Expected 2 responses from batch, got: {len(responses)}")

        ts, ta = responses
        return ta / ts


def check_peg(validator_rate, curve_rate):
    if curve_rate == 0:
        return False
    # Calculate the percentage difference
    difference = abs(validator_rate - curve_rate)
    percentage_diff = difference / validator_rate
    return percentage_diff >= peg_threshold  # 0.06 >= 0.05


def main():
    validator_rate_unscaled = check_steth_validator_rate()
    message = f"🔄 1 stETH is: {validator_rate_unscaled:.5f} ETH in Lido\n"

    amounts = [1e18, 100e18, 1000e18]

    # Create batch request
    with w3.batch_requests() as batch:
        # Add all curve pool requests to the batch
        for amount in amounts:
            batch.add(curve_pool.functions.get_dy(1, 0, int(amount)))
        # Execute all at once and store responses
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

    # Process results outside the batch to save rpc calls
    for amount, curve_rate in zip(amounts, curve_rates):
        try:
            validator_rate_scaled = validator_rate_unscaled * amount
            if curve_rate is not None and check_peg(validator_rate_scaled, curve_rate):
                human_readable_amount = amount / 1e18
                human_readable_result = curve_rate / 1e18
                message += f"📊 Swap result for amount {human_readable_amount:.5f}: {human_readable_result:.5f}"
                send_telegram_message(message, PROTOCOL)
        except Exception as e:
            error_message = (
                f"Error processing curve pool rate for amount {amount/1e18:.2f}: {e}"
            )
            send_telegram_message(error_message, PROTOCOL)


if __name__ == "__main__":
    main()
