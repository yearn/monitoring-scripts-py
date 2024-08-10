import requests
from brownie import Contract, network
from dotenv import load_dotenv
import os

load_dotenv()

safe_apis = {
    "mainnet": "https://safe-transaction-mainnet.safe.global",
    "arbitrum-main": "https://safe-transaction-arbitrum.safe.global",
    "optimism-main": "https://safe-transaction-optimism.safe.global",
    "polygon-main": "https://safe-transaction-polygon.safe.global",
    "optim-yearn": "https://safe-transaction-optimism.safe.global",
}

def get_safe_transactions(safe_address, network_name, executed=None, limit=10):
    base_url = safe_apis[network_name] + "/api/v1"
    endpoint = f"{base_url}/safes/{safe_address}/multisig-transactions/"

    params = {
        "limit": limit,
        "ordering": "-nonce"  # Order by nonce descending
    }

    if executed is not None:
        params["executed"] = str(executed).lower()

    response = requests.get(endpoint, params=params)

    if response.status_code == 200:
        return response.json()['results']
    else:
        print(f"Error: {response.status_code}")
        return None

def get_last_executed_nonce(safe_address, network_name):
    executed_txs = get_safe_transactions(safe_address, network_name, executed=True, limit=1)
    if executed_txs:
        return executed_txs[0]['nonce']
    return -1  # Return -1 if no executed transactions found

def get_pending_transactions_after_last_executed(safe_address, network_name):
    last_executed_nonce = get_last_executed_nonce(safe_address, network_name)
    pending_txs = get_safe_transactions(safe_address, network_name, executed=False)

    if pending_txs:
        return [tx for tx in pending_txs if tx['nonce'] > last_executed_nonce]
    return []


def check_for_pending_transactions(safe_address, network_name, protocol):
    pending_transactions = get_pending_transactions_after_last_executed(safe_address, network_name)

    if pending_transactions:
        network.connect(network_name)
        for tx in pending_transactions:
            target_contract = tx['to']
            calldata = tx['data']
            try:
                res = Contract.from_explorer(target_contract).decode_input(calldata)
                function_details = f"Function Call Details: {res}"
            except Exception as e:
                    function_details = f"Error decoding input: {e}"
            message = (
                "🚨 **PENDING TX DETECTED** 🚨\n"
                f"📜 **Target Contract Address:** {target_contract}\n"
                f"💰 **Value:** {tx['value']}\n"
                f"📅 **Submission Date:** {tx['submissionDate']}\n"
                f"🔍 **Function Call Details:** {function_details}"
            )
            print(message) # print message here for debug
            send_telegram_message(message, protocol)
    else:
        print("No pending transactions found with higher nonce than the last executed transaction.")

def run_for_network(network_name, safe_address, protocol):
    check_for_pending_transactions(safe_address, network_name, protocol)

def send_telegram_message(message, protocol):
    # Dynamically select the bot token and chat ID based on the protocol
    bot_token = os.getenv(f"TELEGRAM_BOT_TOKEN_{protocol.upper()}")
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{protocol.upper()}")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")

def main():
    # combined addresses, add more addresses if needed
    all_safe_addresses = [
        ("STARGATE", "mainnet", "0x65bb797c2B9830d891D87288F029ed8dACc19705"),
        ("STARGATE", "polygon-main", "0x47290DE56E71DC6f46C26e50776fe86cc8b21656"),
        ("STARGATE", "optimism-main", "0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43"),
        ("STARGATE", "arbitrum-main", "0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d"),
        ("SILO", "mainnet", "0xE8e8041cB5E3158A0829A19E014CA1cf91098554"), # TEST: yearn ms in mainnet 0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52
        ("SILO", "optimism-main", "0x468CD12aa9e9fe4301DB146B0f7037831B52382d"),
        ("SILO", "arbitrum-main", "0x865A1DA42d512d8854c7b0599c962F67F5A5A9d9"),
    ]

    # loop all
    for protocol, network_name, safe_address in all_safe_addresses:
        print(f"Running for {protocol} on {network_name}")
        run_for_network(network_name, safe_address, protocol)

if __name__ == "__main__":
    main()
