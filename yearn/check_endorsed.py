#!/usr/bin/env python3
# Summary:
# - Verifies Yearn v3 yDaemon vaults against on-chain isEndorsed for each chain_id.
# - Fetches yDaemon vault metadata per chain and checks each address via the registry contract.
# - Writes any failures to errors.txt as "Chain <chain_id>: <address>".
# Prereqs: Python 3.9+ with requests and web3, plus RPC access to configured endpoints.
import requests
from web3 import Web3

# ChainIDs to test
chain_ids = [1, 137, 8453, 42161, 747474]

# RPC URLs for each chain
rpc_urls = {
    1: "https://eth-mainnet.public.blastapi.io",
    137: "https://polygon.lava.build",
    8453: "https://base.gateway.tenderly.co",
    42161: "https://arbitrum.gateway.tenderly.co",
    747474: "https://katana.drpc.org",
}

# Contract address to check against
registry_address = "0xd40ecF29e001c76Dcc4cC0D9cd50520CE845B038"
registry_checksum = Web3.to_checksum_address(registry_address)
registry_abi = [
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "isEndorsed",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# Store all errors with chain information
all_errors = []
total_checked = 0


print("Verify all yDaemon vaults are isEndorsed in Registry...")

for chain_id in chain_ids:
    print(f"\n{'='*60}")
    print(f"Testing Chain ID: {chain_id}")
    print(f"{'='*60}")

    # Check if RPC URL is configured for this chain
    if chain_id not in rpc_urls:
        print(f"⚠️  No RPC URL configured for chain {chain_id}, skipping...")
        continue

    rpc_url = rpc_urls[chain_id]
    print(f"Using RPC: {rpc_url}")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    registry_contract = w3.eth.contract(address=registry_checksum, abi=registry_abi)

    # Fetch JSON from URL for this chainID
    url = f"https://ydaemon.yearn.fi/vaults/v3?hideAlways=true&strategiesDetails=withDetails&strategiesCondition=inQueue&chainIDs={chain_id}"
    print(f"Fetching data from API...")

    try:
        response = requests.get(url)
        response.raise_for_status()
        vaults = response.json()

        # Extract addresses from the yDaemon JSON response
        ydaemon_addresses = [vault['address'] for vault in vaults if 'address' in vault]
        print(f"Found {len(ydaemon_addresses)} addresses for chain {chain_id}")

        if len(ydaemon_addresses) == 0:
            print(f"No addresses found for chain {chain_id}, skipping...")
            continue

    except requests.RequestException as e:
        print(f"Error fetching data from URL: {e}")
        continue
    except (KeyError, ValueError) as e:
        print(f"Error parsing JSON: {e}")
        continue

    # Check each address
    chain_errors = []
    print()
    print("Checking yDaemon vaults against isEndorsed...")
    print(f"Checking {len(ydaemon_addresses)} addresses...")

    for i, address in enumerate(ydaemon_addresses, 1):
        print(f"  [{i}/{len(ydaemon_addresses)}] Checking: {address}", end=" ")

        try:
            endorsed = registry_contract.functions.isEndorsed(
                Web3.to_checksum_address(address)
            ).call()

            if not endorsed:
                print("❌ Not endorsed")
                chain_errors.append(address)
                all_errors.append(f"Chain {chain_id}: {address}")
            else:
                print("✓")

        except (ValueError, TypeError) as e:
            print(f"❌ Error: {e}")
            chain_errors.append(address)
            all_errors.append(f"Chain {chain_id}: {address}")

    total_checked += len(ydaemon_addresses)
    print(f"\nChain {chain_id} summary: {len(chain_errors)} errors out of {len(ydaemon_addresses)} addresses")

# Write all errors to errors.txt
print(f"\n{'='*60}")
print(f"FINAL SUMMARY")
print(f"{'='*60}")
print(f"Total addresses checked: {total_checked}")
print(f"Total errors found: {len(all_errors)}")
with open('errors.txt', 'w') as f:
    for error in all_errors:
        f.write(f"{error}\n")

print(f"Errors written to errors.txt")