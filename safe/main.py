import requests
from brownie import Contract, network
from dotenv import load_dotenv

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


def check_for_pending_transactions(safe_address, network_name):
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

            print(function_details)
            print(f"Target Contract Address: {target_contract}")
            print(f"Value: {tx['value']}")
            print(f"Submission Date: {tx['submissionDate']}")
            print("---")
            # TODO: send telegram message to specific chat_id?
    else:
        print("No pending transactions found with higher nonce than the last executed transaction.")

def run_for_network(network_name, safe_address):
    print(f"Running for network: {network_name}")
    check_for_pending_transactions(safe_address, network_name)

def main():
    stargate_safe_addresses = {
        "mainnet": "0x65bb797c2B9830d891D87288F029ed8dACc19705",
        "polygon-main": "0x47290DE56E71DC6f46C26e50776fe86cc8b21656",
        "optimism-main": "0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43",
        "arbitrum-main": "0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d",
    }

    for network_name, safe_address in stargate_safe_addresses.items():
        run_for_network(network_name, safe_address)

    # TODO: add other safe addresses for other protocols

if __name__ == "__main__":
    main()