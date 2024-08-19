import requests, os
from brownie import Contract, network
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

SAFE_WEBSITE_URL="https://app.safe.global/transactions/queue?safe="

safe_address_network_prefix = {
    "mainnet": "eth",
    "arbitrum-main": "arb1",
    "optimism-main": "oeth",
    "polygon-main": "matic",
    "optim-yearn": "oeth",
}

safe_apis = {
    "mainnet": "https://safe-transaction-mainnet.safe.global",
    "arbitrum-main": "https://safe-transaction-arbitrum.safe.global",
    "optimism-main": "https://safe-transaction-optimism.safe.global",
    "polygon-main": "https://safe-transaction-polygon.safe.global",
    # "optim-yearn": "https://safe-transaction-optimism.safe.global",
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

def get_safe_url(safe_address, network_name):
    return f"{SAFE_WEBSITE_URL}{safe_address_network_prefix[network_name]}:{safe_address}"

def is_submitted_in_last_hour(submission_date):
    submission_date = datetime.fromisoformat(submission_date.replace("Z", "+00:00"))
    current_date = datetime.now(timezone.utc)
    return (current_date - submission_date).total_seconds() < 3600

def check_for_pending_transactions(safe_address, network_name, protocol):
    pending_transactions = get_pending_transactions_after_last_executed(safe_address, network_name)

    if pending_transactions:
        network.connect(network_name)
        for tx in pending_transactions:
            # Skip if the transaction was submitted more than hour ago because the script is running every hour
            # and we don't want to send duplicate messages
            submission_date = tx['submissionDate']
            if not is_submitted_in_last_hour(submission_date):
                print(f"Skipping safe address: {safe_address} tx nonce: {tx['nonce']} as it was submitted in the last hour.")
                continue

            target_contract = tx['to']
            calldata = tx['data']
            try:
                res = Contract.from_explorer(target_contract).decode_input(calldata)
                function_details = f"Function Call Details: {res}"
            except Exception as e:
                function_details = f"Error decoding input: {e}"
            message = (
                "🚨 **PENDING TX DETECTED** 🚨\n"
                f"🔐 **Safe Address:** {safe_address}\n"
                f"🔗 **Safe URL:** {get_safe_url(safe_address, network_name)}\n"
                f"📜 **Target Contract Address:** {target_contract}\n"
                f"💰 **Value:** {tx['value']}\n"
                f"📅 **Submission Date:** {tx['submissionDate']}\n"
                f"🔍 **Function Call Details:** {function_details}"
            )
            send_telegram_message(message, protocol)
        network.disconnect()
    else:
        print("No pending transactions found with higher nonce than the last executed transaction.")

def run_for_network(network_name, safe_address, protocol):
    check_for_pending_transactions(safe_address, network_name, protocol)

def send_telegram_message(message, protocol):
    print(f"Sending telegram message:\n{message}")
    bot_token = os.getenv(f"TELEGRAM_BOT_TOKEN_{protocol.upper()}")
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{protocol.upper()}")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")

def main():
    # combined addresses, add more addresses if needed
    all_safe_addresses = [
        ["STARGATE", "mainnet", "0x65bb797c2B9830d891D87288F029ed8dACc19705"],
        ["STARGATE", "polygon-main", "0x47290DE56E71DC6f46C26e50776fe86cc8b21656"],
        ["STARGATE", "optimism-main", "0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43"],
        ["STARGATE", "arbitrum-main", "0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d"],
        ["SILO", "mainnet", "0xE8e8041cB5E3158A0829A19E014CA1cf91098554"],
        ["SILO", "optimism-main", "0x468CD12aa9e9fe4301DB146B0f7037831B52382d"],
        ["SILO", "arbitrum-main", "0x865A1DA42d512d8854c7b0599c962F67F5A5A9d9"],
        ["LIDO", "mainnet", "0x73b047fe6337183A454c5217241D780a932777bD"], # https://docs.lido.fi/multisigs/emergency-brakes/#12-emergency-brakes-ethereum
        ["LIDO", "mainnet", "0x8772E3a2D86B9347A2688f9bc1808A6d8917760C"], # https://docs.lido.fi/multisigs/emergency-brakes/#11-gateseal-committee -> expires on 1 April 2025.
        # TEST: yearn ms in mainnet 0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52
    ]

    # loop all
    for safe in all_safe_addresses:
        print(f"Running for {safe[0]} on {safe[1]}")
        run_for_network(safe[1], safe[2], safe[0])

if __name__ == "__main__":
    main()
