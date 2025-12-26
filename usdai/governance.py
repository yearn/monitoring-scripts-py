import os
import sys
from web3 import Web3
from dotenv import load_dotenv

from utils.chains import Chain
from utils.web3_wrapper import ChainManager
from utils.telegram import send_telegram_message
from utils.cache import (
    get_last_value_for_key_from_file, 
    write_last_value_to_file, 
    cache_filename
)

load_dotenv()

PROTOCOL = "usdai"

# Contracts to monitor
CONTRACTS = {
    "USDai Vault": "0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF",
    "USDai Token": "0x0B2b2B2076d95dda7817e785989fE353fe955ef9",
    "wM Token": "0x437cc33344a0b27a429f795ff6b469c72698b291"
}

# Standard Governance Events Topics
EVENTS = {
    # AccessControl: RoleGranted(bytes32 role, address account, address sender)
    "RoleGranted": "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d",
    # AccessControl: RoleRevoked(bytes32 role, address account, address sender)
    "RoleRevoked": "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b",
    # Proxy: Upgraded(address implementation)
    "Upgraded": "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b",
    # Proxy: AdminChanged(address previousAdmin, address newAdmin)
    "AdminChanged": "0x7e644d79422f17c01e4894b5f4f588d331ebfa28653d42ae832dc59e38c9798f",
    # Ownable: OwnershipTransferred(address previousOwner, address newOwner)
    "OwnershipTransferred": "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0",
    # SupplyCapSet(uint256 newSupplyCap)
    "SupplyCapSet": "0xbc585eed6f54aa16ec292be93276937803d5a047ba4eded0c87779270bbfdfe6"
}

def main():
    client = ChainManager.get_client(Chain.ARBITRUM)
    
    current_block = client.eth.block_number
    cache_key = f"{PROTOCOL}_governance_last_block"
    last_block_str = get_last_value_for_key_from_file(cache_filename, cache_key)
    
    # If no cache, look back 100 blocks to initialize, or use a manual start if needed.
    start_block = int(last_block_str) + 1 if last_block_str and int(last_block_str) > 0 else current_block - 100
    
    # Safety cap: Reduce max scan range significantly due to strict RPC limits
    MAX_BLOCK_RANGE = 2000
    if current_block - start_block > MAX_BLOCK_RANGE:
        current_block = start_block + MAX_BLOCK_RANGE # Only scan up to MAX_BLOCK_RANGE from start
        
    print(f"Scanning for governance events from block {start_block} to {current_block}...")

    # Further split into smaller chunks for the actual RPC calls
    CHUNK_SIZE = 500
    
    events_found = 0
    
    for chunk_start in range(start_block, current_block + 1, CHUNK_SIZE):
        chunk_end = min(chunk_start + CHUNK_SIZE - 1, current_block)
        print(f"  Processing chunk {chunk_start} to {chunk_end}...")
        
        for name, address in CONTRACTS.items():
            checksum_addr = Web3.to_checksum_address(address)
            
            # Fetch logs for each event topic
            for event_name, topic in EVENTS.items():
                try:
                    # Robust retry logic
                    max_retries = 5
                    logs = []
                    for attempt in range(max_retries):
                        try:
                            logs = client.eth.get_logs({
                                "fromBlock": chunk_start,
                                "toBlock": chunk_end,
                                "address": checksum_addr,
                                "topics": [topic]
                            })
                            break # Success
                        except Exception as e:
                            if attempt == max_retries - 1:
                                print(f"    Failed to fetch logs for {name} ({event_name}) after {max_retries} attempts. Error: {e}")
                                # Don't raise, try to continue to next event/contract but log error
                            import time
                            wait_time = 2 * (attempt + 1)
                            # print(f"    Rpc error, retrying in {wait_time}s...")
                            time.sleep(wait_time) 

                    for log in logs:
                        events_found += 1
                        tx_hash = log['transactionHash'].hex()
                        msg = f"🚨 *USDai Governance Alert*\n\n" \
                              f"Event: {event_name}\n" \
                              f"Contract: {name}\n" \
                              f"Address: {address}\n" \
                              f"Tx: [Arbiscan](https://arbiscan.io/tx/{tx_hash})"
                        
                        print(msg)
                        send_telegram_message(msg, PROTOCOL)
                        
                except Exception as e:
                    print(f"Error scanning {name} for {event_name}: {e}")

    if events_found == 0:
        print("No governance events found in this range.")

    # Update cache with the block we successfully scanned up to
    write_last_value_to_file(cache_filename, cache_key, current_block)

if __name__ == "__main__":
    main()
