import requests, os
from dotenv import load_dotenv
from utils.cache import (
    get_last_executed_nonce_from_file,
    write_last_executed_nonce_to_file,
)
from utils.telegram import send_telegram_message
from safe.specific import handle_pendle

load_dotenv()

SAFE_WEBSITE_URL = "https://app.safe.global/transactions/queue?safe="
provider_url_mainnet = os.getenv("PROVIDER_URL_MAINNET")
provider_url_arb = os.getenv("PROVIDER_URL_ARBITRUM")

safe_address_network_prefix = {
    "mainnet": "eth",
    "arbitrum-main": "arb1",
    "optimism-main": "oeth",
    "polygon-main": "matic",
    "optim-yearn": "oeth",
    "base-main": "base",
}

safe_apis = {
    "mainnet": "https://safe-transaction-mainnet.safe.global",
    "arbitrum-main": "https://safe-transaction-arbitrum.safe.global",
    "optimism-main": "https://safe-transaction-optimism.safe.global",
    "polygon-main": "https://safe-transaction-polygon.safe.global",
    "base-main": "https://safe-transaction-polygon.safe.global",
    # "optim-yearn": "https://safe-transaction-optimism.safe.global",
}


def get_safe_transactions(safe_address, network_name, executed=None, limit=10):
    base_url = safe_apis[network_name] + "/api/v1"
    endpoint = f"{base_url}/safes/{safe_address}/multisig-transactions/"

    params = {"limit": limit, "ordering": "-nonce"}  # Order by nonce descending

    if executed is not None:
        params["executed"] = str(executed).lower()

    response = requests.get(endpoint, params=params)

    if response.status_code == 200:
        return response.json()["results"]
    else:
        print(f"Error: {response.status_code}")
        return None


def get_last_executed_nonce(safe_address, network_name):
    executed_txs = get_safe_transactions(
        safe_address, network_name, executed=True, limit=1
    )
    if executed_txs:
        return executed_txs[0]["nonce"]
    return -1  # Return -1 if no executed transactions found


def get_pending_transactions_after_last_executed(safe_address, network_name):
    last_executed_nonce = get_last_executed_nonce(safe_address, network_name)
    pending_txs = get_safe_transactions(safe_address, network_name, executed=False)

    if pending_txs:
        return [tx for tx in pending_txs if tx["nonce"] > last_executed_nonce]
    return []


def get_safe_url(safe_address, network_name):
    return (
        f"{SAFE_WEBSITE_URL}{safe_address_network_prefix[network_name]}:{safe_address}"
    )


def check_for_pending_transactions(safe_address, network_name, protocol):
    pending_transactions = get_pending_transactions_after_last_executed(
        safe_address, network_name
    )

    if pending_transactions:
        for tx in pending_transactions:
            nonce = int(tx["nonce"])
            # skip tx if the nonce is already processed
            if nonce <= get_last_executed_nonce_from_file(safe_address):
                print(f"Skipping tx with nonce {nonce} as it is already processed.")
                continue

            target_contract = tx["to"]
            message = (
                "🚨 QUEUED TX DETECTED 🚨\n"
                f"🅿️ Protocol: {protocol}\n"
                f"🔐 Safe Address: {safe_address}\n"
                f"🔗 Safe URL: {get_safe_url(safe_address, network_name)}\n"
                f"📜 Target Contract Address: {target_contract}\n"
                f"💰 Value: {tx['value']}\n"
                f"📅 Submission Date: {tx['submissionDate']}\n"
            )

            # pendle uses specific owner of the contracts where we need to decode the data
            if protocol == "PENDLE":
                hex_data = tx["data"]
                try:
                    if network_name == "mainnet":
                        message += handle_pendle(provider_url_mainnet, hex_data)
                    elif network_name == "arbitrum-main":
                        message += handle_pendle(provider_url_arb, hex_data)
                except Exception as e:
                    print(f"Cannot decode Pendle aggregate calls: {e}")

            send_telegram_message(
                message, protocol, False
            )  # explicitly enable notification
            # write the last executed nonce to file
            write_last_executed_nonce_to_file(safe_address, nonce)
    else:
        print(
            "No pending transactions found with higher nonce than the last executed transaction."
        )


def run_for_network(network_name, safe_address, protocol):
    check_for_pending_transactions(safe_address, network_name, protocol)


def main():
    # combined addresses, add more addresses if needed
    all_safe_addresses = [
        ["SILO", "mainnet", "0xE8e8041cB5E3158A0829A19E014CA1cf91098554"],
        # ["SILO", "optimism-main", "0x468CD12aa9e9fe4301DB146B0f7037831B52382d"],
        ["SILO", "arbitrum-main", "0x865A1DA42d512d8854c7b0599c962F67F5A5A9d9"],
        [
            "LIDO",
            "mainnet",
            "0x73b047fe6337183A454c5217241D780a932777bD",
        ],  # https://docs.lido.fi/multisigs/emergency-brakes/#12-emergency-brakes-ethereum
        [
            "LIDO",
            "mainnet",
            "0x8772E3a2D86B9347A2688f9bc1808A6d8917760C",
        ],  # https://docs.lido.fi/multisigs/emergency-brakes/#11-gateseal-committee -> expires on 1 April 2025.
        ["PENDLE", "mainnet", "0x8119EC16F0573B7dAc7C0CB94EB504FB32456ee1"],
        ["PENDLE", "arbitrum-main", "0x7877AdFaDEd756f3248a0EBfe8Ac2E2eF87b75Ac"],
        ["EULER", "mainnet", "0xcAD001c30E96765aC90307669d578219D4fb1DCe"],
        [
            "AAVE",
            "mainnet",
            "0x2CFe3ec4d5a6811f4B8067F0DE7e47DfA938Aa30",
        ],  # aave Protocol Guardian Safe: https://app.aave.com/governance/v3/proposal/?proposalId=184
        ["AAVE", "polygon-main", "0xCb45E82419baeBCC9bA8b1e5c7858e48A3B26Ea6"],
        ["AAVE", "arbitrum-main", "0xCb45E82419baeBCC9bA8b1e5c7858e48A3B26Ea6"],
        [
            "AAVE",
            "mainnet",
            "0xCe52ab41C40575B072A18C9700091Ccbe4A06710",
        ],  # aave Governance Guardian Safe
        ["AAVE", "polygon-main", "0x1A0581dd5C7C3DA4Ba1CDa7e0BcA7286afc4973b"],
        ["AAVE", "arbitrum-main", "0x1A0581dd5C7C3DA4Ba1CDa7e0BcA7286afc4973b"],
        [
            "MOONWELL",
            "base-main",
            "0x446342AF4F3bCD374276891C6bb3411bf2F8779E",
        ],  # admin of timelock controller
        [
            "MOONWELL",
            "base-main",
            "0xB9d4acf113a423Bc4A64110B8738a52E51C2AB38",
        ],  # pause guardian of comptroller contract
        [
            "USD0",
            "mainnet",
            "0x6e9d65eC80D69b1f508560Bc7aeA5003db1f7FB7",
        ],  # USD0 protocol governance
        # no active stargate strategies
        # ["STARGATE", "mainnet", "0x65bb797c2B9830d891D87288F029ed8dACc19705"],
        # ["STARGATE", "polygon-main", "0x47290DE56E71DC6f46C26e50776fe86cc8b21656"],
        # ["STARGATE", "optimism-main", "0x392AC17A9028515a3bFA6CCe51F8b70306C6bd43"],
        # ["STARGATE", "arbitrum-main", "0x9CD50907aeb5D16F29Bddf7e1aBb10018Ee8717d"],
        # TEST: yearn ms in mainnet 0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52
    ]

    # loop all
    for safe in all_safe_addresses:
        print(f"Running for {safe[0]} on {safe[1]}")
        run_for_network(safe[1], safe[2], safe[0])


if __name__ == "__main__":
    main()
