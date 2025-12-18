from utils.abi import load_abi
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

CUSD = "0xcCcc62962d17b8914c62D74FfB843d73B2a3cccC"
PROTOCOL = "cap"
ALERT_THRESHOLD=100_000_000 # 100M

def main():
    client = ChainManager.get_client(Chain.MAINNET)

    ctoken = client.eth.contract(address=CUSD, abi=load_abi("cap/abi/CToken.json"))  # aka cusd

    assets = ctoken.functions.assets().call()

    # Batch 1: resolve vault addresses for each asset
    with client.batch_requests() as batch:
        for asset in assets:
            batch.add(ctoken.functions.fractionalReserveVault(asset))
        vault_addresses = batch.execute()

    # Batch 2: for each asset, get vault maxWithdraw for CUSD owner, token balance, decimals, and symbol
    with client.batch_requests() as batch:
        for asset, vault_addr in zip(assets, vault_addresses):
            vault = client.eth.contract(address=vault_addr, abi=load_abi("cap/abi/YearnV3Vault.json"))
            token = client.eth.contract(address=asset, abi=load_abi("common-abi/ERC20.json"))
            batch.add(vault.functions.maxWithdraw(CUSD))
            batch.add(token.functions.balanceOf(CUSD))
            batch.add(token.functions.decimals())
            batch.add(token.functions.symbol())
        responses = batch.execute()

    # Parse batched results (4 entries per asset)
    lines = []
    total_normalized = 0
    for i in range(0, len(responses), 4):
        vault_withdrawable = responses[i] or 0
        direct_balance = responses[i + 1] or 0
        decimals = responses[i + 2] if responses[i + 2] is not None else 18
        symbol = responses[i + 3] or "UNKNOWN"

        total_units = int(vault_withdrawable) + int(direct_balance)
        
        divisor = 10 ** int(decimals)
        normalized = total_units / divisor if divisor else 0
        line = f"{symbol}: {normalized:,.6f}"
        total_normalized += normalized
        lines.append(line)

    if total_normalized < ALERT_THRESHOLD:
        message = "💧 CAP Withdrawable Liquidity (Mainnet)\n" + "\n".join(lines)
        send_telegram_message(message, PROTOCOL, False)


if __name__ == "__main__":
    main()
