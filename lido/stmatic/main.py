from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

peg_threshold = 0.05 # 5%
provider_url = os.getenv("PROVIDER_URL_MAINNET")
provider_url_polygon = os.getenv("PROVIDER_URL")
w3 = Web3(Web3.HTTPProvider(provider_url))
w3_polygon = Web3(Web3.HTTPProvider(provider_url_polygon))
ASSET_BONDS_EXCEEDED = "GYR#357" # https://github.com/gyrostable/gyro-pools/blob/24060707809123e1ffd222eba99a5694e4b074c7/tests/geclp/util.py#L419

with open("lido/stmatic/abi/StMatic.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_stmatic = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_stmatic = abi_data

stmatic = w3.eth.contract(address="0x9ee91F9f426fA633d227f7a9b000E28b9dfd8599", abi=abi_stmatic)

with open("common-abi/BalancerQuery.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_bq = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_bq = abi_data

with open("common-abi/BalancerVault.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_bv = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_bv = abi_data

balancer_query = w3_polygon.eth.contract(address="0xE39B5e3B6D74016b2F6A9673D7d7493B6DF549d5", abi=abi_bq)
balancer_vault = w3_polygon.eth.contract(address="0xBA12222222228d8Ba445958a75a0704d566BF2C8", abi=abi_bv)

balancer_pool_id = "0xf0ad209e2e969eaaa8c882aac71f02d8a047d5c2000200000000000000000b49"

single_swap_template = {
    "poolId": balancer_pool_id, # gyroscope concentraded pool
    "kind": 0,  # 0 for GIVEN_IN
    "assetIn": "0x3A58a54C066FdC0f2D55FC9C89F0415C92eBf3C4", # stmatic
    "assetOut": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # matic
    "amount": 0,  # will be dynamically set
    "userData": b""
}

fund_management = {
    "sender": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    "fromInternalBalance": False,
    "recipient": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    "toInternalBalance": False
}

def send_telegram_message(message):
    print(f"Sending telegram message:\n{message}")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_LIDO")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_LIDO")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message, "disable_notification": True}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")

def query_swap(single_swap, fund_management):
    try:
        swap_res = balancer_query.functions.querySwap(single_swap, fund_management).call()
        return swap_res
    except Exception as e:
        message = ""
        if ASSET_BONDS_EXCEEDED in str(e):
            message = f"⚠️ Asset bonds exceeded in balancer pool ⚠️ \n"
        else:
            message = f"Error calling query in balancer pool: {e}\n"

        # get the balances in the pool in case of error
        try:
            amounts = balancer_vault.functions.getPoolTokens(balancer_pool_id).call()[1]
            matic_balance = amounts[0] / 1e18
            stmatic_balance = amounts[1] / 1e18
            total_balance = matic_balance + stmatic_balance
            matic_percentage = round(matic_balance / total_balance * 100, 2)
            message += (
                f"MATIC balance in the balancer pool: {int(matic_balance)} ({matic_percentage}%)\n"
                f"stMATIC balance in the balancer pool: {int(stmatic_balance)} ({100 - matic_percentage}%)\n"
            )
        except Exception as e:
            message += f"Error querying balances in pool: {e}"
        send_telegram_message(message)

def check_peg(validator_rate, balancer_rate):
    if balancer_rate == 0:
        return False
    # Calculate the percentage difference
    difference = abs(validator_rate - balancer_rate)
    percentage_diff = difference / validator_rate
    return percentage_diff >= peg_threshold # 0.06 >= 0.05

def main():
    validator_rate = int(stmatic.functions.convertStMaticToMatic(10**18).call()[0])
    human_readable_res = validator_rate / 1e18
    message = f"🔄 1 StMATIC is: {human_readable_res:.5f} MATIC in Lido\n"

    # 1 stMATIC, 1000 stMATIC, 100K stMATIC
    # spot price, med amount, big amount
    amounts = [1e18, 100e18, 10_000e18] # TODO: Make these dynamic, maybe add it to env and change it there

    for amount in amounts:
        single_swap = single_swap_template.copy()
        single_swap['amount'] = int(amount)
        validator_rate = human_readable_res * amount
        balancer_rate = query_swap(single_swap, fund_management)
        if balancer_rate is None:
            # break the loop if there is no rate
            # if the first amount is without rate others are also
            break
        if check_peg(validator_rate, balancer_rate):
            human_readable_amount = amount / 1e18
            human_readable_result = balancer_rate / 1e18
            message += f"📊 Swap result for amount {human_readable_amount:.5f}: {human_readable_result:.5f}"
            send_telegram_message(message)

if __name__ == "__main__":
    main()