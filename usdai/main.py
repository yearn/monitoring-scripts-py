import os
import sys
import requests
import json
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

# Constants
PROTOCOL = "usdai"
VAULT_ADDR = Web3.to_checksum_address("0x0A1a1A107E45b7Ced86833863f482BC5f4ed82EF")
WM_TOKEN = Web3.to_checksum_address("0x437cc33344a0b27a429f795ff6b469c72698b291")
SUSDAI_ADDR = Web3.to_checksum_address("0x0B2b2B2076d95dda7817e785989fE353fe955ef9")

# Storage Slots
IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

def get_address_from_slot(client, contract_address, slot):
    try:
        data = client.eth.get_storage_at(contract_address, slot).hex()
        return Web3.to_checksum_address("0x" + data[-40:])
    except Exception as e:
        print(f"Error reading slot {slot}: {e}")
        return None

def check_role(client, contract, role_name, func_name, cache_key_suffix):
    try:
        current_value = getattr(contract.functions, func_name)().call()
    except Exception as e:
        return

    cache_key = f"{PROTOCOL}_{cache_key_suffix}"
    last_value = get_last_value_for_key_from_file(cache_filename, cache_key)
    
    if last_value == 0:
        write_last_value_to_file(cache_filename, cache_key, current_value)
        return

    if str(last_value).lower() != current_value.lower():
        msg = f"⚠️ *USDai {role_name} Changed*\n\nOld: `{last_value}`\nNew: `{current_value}`"
        send_telegram_message(msg, PROTOCOL)
        write_last_value_to_file(cache_filename, cache_key, current_value)

def check_proxy_admin(client, address):
    cache_key_impl = f"{PROTOCOL}_implementation"
    cache_key_admin = f"{PROTOCOL}_proxy_admin"
    
    current_impl = get_address_from_slot(client, address, IMPLEMENTATION_SLOT)
    current_admin = get_address_from_slot(client, address, ADMIN_SLOT)
    
    if current_impl:
        last_impl = get_last_value_for_key_from_file(cache_filename, cache_key_impl)
        if last_impl != 0 and str(last_impl).lower() != current_impl.lower():
            msg = f"⚠️ *USDai Implementation Upgraded*\n\nOld: `{last_impl}`\nNew: `{current_impl}`"
            send_telegram_message(msg, PROTOCOL)
        if last_impl == 0 or str(last_impl).lower() != current_impl.lower():
            write_last_value_to_file(cache_filename, cache_key_impl, current_impl)

    if current_admin:
        last_admin = get_last_value_for_key_from_file(cache_filename, cache_key_admin)
        if last_admin != 0 and str(last_admin).lower() != current_admin.lower():
            msg = f"⚠️ *USDai Proxy Admin Changed*\n\nOld: `{last_admin}`\nNew: `{current_admin}`"
            send_telegram_message(msg, PROTOCOL)
        if last_admin == 0 or str(last_admin).lower() != current_admin.lower():
            write_last_value_to_file(cache_filename, cache_key_admin, current_admin)

def main():
    client = ChainManager.get_client(Chain.ARBITRUM)
    
    # Common ABI
    erc20_abi = [
        {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"type": "address"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"}
    ]
    
    # Vault / Roles ABI
    roles_abi = erc20_abi + [
        {"inputs": [], "name": "owner", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "pauser", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "blacklister", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "rescuer", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"}
    ]

    usdai = client.get_contract(VAULT_ADDR, roles_abi)
    wm = client.get_contract(WM_TOKEN, erc20_abi)
    
    try:
        # --- On-Chain Supply ---
        # wM Total Supply
        wm_total_supply = wm.functions.totalSupply().call()
        # USDai Supply (wM held by Vault)
        vault_shares = wm.functions.balanceOf(VAULT_ADDR).call()
        
        wm_decimals = wm.functions.decimals().call()
        
        usdai_supply_fmt = vault_shares / (10 ** wm_decimals)
        wm_total_supply_fmt = wm_total_supply / (10 ** wm_decimals)
        
        # sUSDai holdings of wM (wM balance of sUSDai contract)
        try:
             susdai_wm_balance = wm.functions.balanceOf(SUSDAI_ADDR).call()
             susdai_wm_balance_fmt = susdai_wm_balance / (10 ** wm_decimals)
        except Exception as e:
             print(f"Error fetching sUSDai balance: {e}")
             susdai_wm_balance_fmt = 0

        # Buffer Calculation
        # Buffer = wM Total Supply - USDai Supply - sUSDai Holdings
        # buffer = wm_total_supply_fmt - usdai_supply_fmt - susdai_wm_balance_fmt
        
        print(f"\n--- USDai Stats ---")
        print(f"USDai Supply:    ${usdai_supply_fmt:,.2f}")
        
        tbill_backing = wm_total_supply_fmt - susdai_wm_balance_fmt
        print(f"TBILL BACKING:   ${tbill_backing:,.2f}")

        buffer = tbill_backing - usdai_supply_fmt
        print(f"Buffer:          ${buffer:,.2f}")

        
        if usdai_supply_fmt > 0:
            ratio = tbill_backing / usdai_supply_fmt
            print(f"Ratio:           {ratio * 100:.4f}%")

            # Check for swings
            cache_key_ratio = f"{PROTOCOL}_ratio"
            # get_last_value_for_key_from_file returns a string or 0
            last_ratio_str = get_last_value_for_key_from_file(cache_filename, cache_key_ratio)
            last_ratio = float(last_ratio_str) if last_ratio_str != 0 else 0.0

            if last_ratio == 0:
                write_last_value_to_file(cache_filename, cache_key_ratio, ratio)
            else:
                change = ratio - last_ratio
                # If drop is >= 0.05% (0.0005)
                if change <= -0.0005:
                    msg = f"📉 *USDai Ratio Swing Alert*\n\nRatio dropped by {change*100:.4f}%!\nOld: {last_ratio*100:.4f}%\nNew: {ratio*100:.4f}%"
                    send_telegram_message(msg, PROTOCOL)
                    write_last_value_to_file(cache_filename, cache_key_ratio, ratio)
                # Update baseline on significant rise as well
                elif change >= 0.0005:
                     write_last_value_to_file(cache_filename, cache_key_ratio, ratio)


        
    except Exception as e:
        print(f"Error: {e}")
        send_telegram_message(f"⚠️ USDai monitoring failed: {e}", PROTOCOL)

    # --- Governance Monitoring ---
    check_proxy_admin(client, VAULT_ADDR)
    check_role(client, usdai, "Owner", "owner", "owner")
    check_role(client, usdai, "Pauser", "pauser", "pauser")
    check_role(client, usdai, "Blacklister", "blacklister", "blacklister")
    check_role(client, usdai, "Rescuer", "rescuer", "rescuer")

if __name__ == "__main__":
    main()
