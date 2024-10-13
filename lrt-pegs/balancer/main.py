from web3 import Web3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()

peg_threshold = 0.05 # 5%
provider_url = os.getenv("PROVIDER_URL_MAINNET")
w3 = Web3(Web3.HTTPProvider(provider_url))
w3_mainnet = Web3(Web3.HTTPProvider(provider_url))

ASSET_BONDS_EXCEEDED = "GYR#357" # https://github.com/gyrostable/gyro-pools/blob/24060707809123e1ffd222eba99a5694e4b074c7/tests/geclp/util.py#L419

PEG_THRESHOLD = 1

with open("common-abi/BalancerVault.json") as f:
    abi_data = json.load(f)
    if isinstance(abi_data, dict):
        abi_bv = abi_data["result"]
    elif isinstance(abi_data, list):
        abi_bv = abi_data

balancer_vault = w3_mainnet.eth.contract(address="0xBA12222222228d8Ba445958a75a0704d566BF2C8", abi=abi_bv)

ids = [
    # name, pool id, index of lrt, is BPT token an underlying token of the balancer pool?
    ("Renzo ezETH-WETH 50-50 Pool", "0x596192bb6e41802428ac943d2f1476c1af25cc0e000000000000000000000659", 1, True),
    ("Kelp rsETH-WETH 50-50 Pool", "0x58aadfb1afac0ad7fca1148f3cde6aedf5236b6d00000000000000000000067f", 1, True),
    # Add more pool names and IDs here as needed in the future
]

def send_telegram_message(message):
    #print(f"Sending telegram message:\n{message}")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_PEGS")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_PEGS")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")


def check_peg(pool_name, pool_id, idx_lrt, is_nested):
    (_, balances, _) = balancer_vault.functions.getPoolTokens(pool_id).call()
    
    total = 0
    start_index = 1 if is_nested else 0

    for i in range(start_index, len(balances)):
        total += balances[i]

    percentage = (balances[idx_lrt] / total) * 100
    if percentage > PEG_THRESHOLD:
        message = f"🚨 Balancer Alert! {pool_name} ratio is {percentage:.2f}% 🚀 Exceeds threshold! ⚠️"
        send_telegram_message(message)
        print(message)


def main():
    print("Checking for pools...")
    
    # Loop through each pool and check its peg
    for pool_name, pool_id, idx_lrt, is_nested in ids:
        check_peg(pool_name, pool_id, idx_lrt, is_nested)

if __name__ == "__main__":
    main()

    