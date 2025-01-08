import json
from utils.web3_wrapper import ChainManager
from utils.chains import Chain
from utils.telegram import send_telegram_message

PROTOCOL = "USD0"
peg_threshold = 0.001  # 0.1% used

# Load ABI
with open("common-abi/CurvePool.json") as f:
    abi_data = json.load(f)
    abi_curve_pool = abi_data["result"] if isinstance(abi_data, dict) else abi_data


def check_peg(usdc_rate, curve_rate):
    if curve_rate == 0:
        return False
    difference = abs(usdc_rate - curve_rate)
    percentage_diff = difference / usdc_rate
    return percentage_diff >= peg_threshold


def check_peg_usd0():
    amounts = [100_000e18, 1_000_000e18, 10_000_000e18]
    message = ""

    # Get Web3 client for mainnet
    client = ChainManager.get_client(Chain.MAINNET)

    # Initialize curve pool contract
    curve_pool = client.eth.contract(
        address="0x14100f81e33C33Ecc7CDac70181Fb45B6E78569F", abi=abi_curve_pool
    )

    # Execute individual requests
    curve_rates = []
    for amount in amounts:
        try:
            rate = curve_pool.functions.get_dy(0, 1, int(amount)).call()
            curve_rates.append(rate)
        except Exception as e:
            error_message = f"Error executing curve pool call: {e}"
            send_telegram_message(error_message, PROTOCOL)
            return

    # Process results
    for amount, curve_rate in zip(amounts, curve_rates):
        if curve_rate is not None and check_peg(amount / 1e12, curve_rate):
            human_readable_amount = amount / 1e18
            human_readable_result = curve_rate / 1e6
            message += f"📊 Swap result: {human_readable_amount:.2f} USD0 -> {human_readable_result:.2f} USDC\n"

    if len(message) > 0:
        send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    check_peg_usd0()
