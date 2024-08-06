import requests
from brownie import Contract
from dotenv import load_dotenv

load_dotenv()

# for mainnet: brownie run safe/main.py --network mainnet

def get_safe_transactions(safe_address, executed=None, limit=10):
    base_url = "https://safe-transaction-mainnet.safe.global/api/v1"
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

def get_last_executed_nonce(safe_address):
    executed_txs = get_safe_transactions(safe_address, executed=True, limit=1)
    if executed_txs:
        return executed_txs[0]['nonce']
    return -1  # Return -1 if no executed transactions found

def get_pending_transactions_after_last_executed(safe_address):
    last_executed_nonce = get_last_executed_nonce(safe_address)
    pending_txs = get_safe_transactions(safe_address, executed=False)

    if pending_txs:
        return [tx for tx in pending_txs if tx['nonce'] > last_executed_nonce]
    return []


def check_for_pending_transactions(safe_address):
    pending_transactions = get_pending_transactions_after_last_executed(safe_address)

    if pending_transactions:
        print(f"Pending transactions with nonce higher than {get_last_executed_nonce(safe_address)}:")
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
    else:
        print("No pending transactions found with higher nonce than the last executed transaction.")

def main():
    safe_address = "0xfE30CaD51Ad8990c3852Ff4798b4A27827E02e5b"  # Replace with your Safe address
    check_for_pending_transactions(safe_address)

# Run the main function
if __name__ == "__main__":
    main()
