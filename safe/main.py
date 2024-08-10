import requests
from brownie import Contract, network
from dotenv import load_dotenv
import subprocess
import os

load_dotenv()

# for mainnet: brownie run safe/main.py --network mainnet

def get_safe_transactions(safe_address, executed=None, limit=10):
    base_url = "https://safe-transaction-optimism.safe.global/api/v1"
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
        network.connect('optimism-main', rpc_url=os.getenv("PROVIDER_URL_OPTIMISM"))
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

def run_script(safe_address):
    check_for_pending_transactions(safe_address)

def run_for_network(network_name, safe_address):
    print(f"Running for network: {network_name}")

    # os.chdir("..")

    # Correct the path to your script
    # script_path = os.path.abspath("./main.py")  # Adjusted to correct path

    # # Run the Brownie command with the correct path
    # command = ["brownie", "run", script_path, "--network", network_name]
    # result = subprocess.run(command, capture_output=True, text=True)

    # # Print output from the command
    # print(result.stdout)
    # if result.stderr:
    #     print(f"Error on {network_name}:\n{result.stderr}")

    # Run the main script logic after Brownie command
    run_script(safe_address)


def main():
    # os.chdir("..")

    networks = {
        # "mainnet": "0x65bb797c2B9830d891D87288F029ed8dACc19705",
        # "polygon-main": "0x47290DE56E71DC6f46C26e50776fe86cc8b21656",
        # "optimism-main": "0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43",
        # "arbitrum-main": "0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d",
        "optim-yearn": "0xea3a15df68fCdBE44Fdb0DB675B2b3A14a148b26"
    }

    for network, safe_address in networks.items():
        run_for_network(network, safe_address)

if __name__ == "__main__":
    main()