from web3 import Web3, constants
from dotenv import load_dotenv
import os
import json
import requests

load_dotenv()

peg_threshold = 0.05 # 5% used
provider_url = os.getenv("PROVIDER_URL_MAINNET")
w3 = Web3(Web3.HTTPProvider(provider_url))

with open("./abi/CurvePool.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_curve_pool = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_curve_pool = abi_data

with open("./abi/Steth.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_steth = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_steth = abi_data


steth = w3.eth.contract(address="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", abi=abi_steth)
curve_pool = w3.eth.contract(address="0xDC24316b9AE028F1497c275EB9192a3Ea0f67022", abi=abi_curve_pool)

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_LIDO")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_LIDO")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")


def check_steth_validator_rate():
    ts = steth.functions.totalSupply().call()
    ta = steth.functions.getTotalPooledEther().call()
    return ta / ts

def check_steth_crv_pool_rate(amount_in):
    return curve_pool.functions.get_dy(1, 0, int(amount_in)).call()

def check_peg(validator_rate, curve_rate):
    if curve_rate == 0:
        return False
    # Calculate the percentage difference
    difference = abs(validator_rate - curve_rate)
    percentage_diff = difference / validator_rate
    return percentage_diff >= peg_threshold # 0.06 >= 0.05

def main():
    validator_rate_unscaled = check_steth_validator_rate() #  for 1 stETH in not 18 decimals
    first_message = f"🔄 1 stETH is: {validator_rate_unscaled:.5f} ETH in Lido"

    amounts = [1e18, 100e18, 1000e18]

    for amount in amounts:
        curve_rate = check_steth_crv_pool_rate(amount) # in 18 decimals
        validator_rate_scaled = validator_rate_unscaled * amount
        if curve_rate is not None and check_peg(validator_rate_scaled, curve_rate):
            human_readable_amount = amount / 1e18
            human_readable_result = curve_rate / 1e18
            message = f"📊 Swap result for amount {human_readable_amount:.5f}: {human_readable_result:.5f}"
            # print(message)
            send_telegram_message(first_message)
            send_telegram_message(message)

if __name__ == "__main__":
    main()