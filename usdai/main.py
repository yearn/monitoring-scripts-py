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

def main():
    client = ChainManager.get_client(Chain.ARBITRUM)
    
    # Common ABI
    erc20_abi = [
        {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
        {"inputs": [{"type": "address"}], "name": "balanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"}
    ]
    
    # Vault / Roles ABI - Only needed for Vault Address check if we were using it for governance, 
    # but we are using it for balanceOf which is in erc20_abi. 
    # Actually, the Vault is not an ERC20 itself, but we are checking wM balance OF the vault.
    # So we just need the wM contract with ERC20 ABI.
    
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

if __name__ == "__main__":
    main()
