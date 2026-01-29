from dotenv import load_dotenv
from web3 import Web3

from utils.cache import cache_filename, get_last_value_for_key_from_file, write_last_value_to_file
from utils.chains import Chain
from utils.telegram import send_telegram_message
from utils.web3_wrapper import ChainManager

load_dotenv()

PROTOCOL = "infinifi"

TIMELOCKS = {
    "TIMELOCK_SHORT": Web3.to_checksum_address("0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32"),
    "TIMELOCK_LONG": Web3.to_checksum_address("0x3D18480CC32B6AB3B833dCabD80E76CfD41c48a9"),
}

DEPLOYER = Web3.to_checksum_address("0xdecaDAc8778D088A30eE811b8Cc4eE72cED9Bf22")

# Minimal ABI for CallScheduled and CallExecuted events
TIMELOCK_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "id", "type": "bytes32"},
            {"indexed": True, "internalType": "uint256", "name": "index", "type": "uint256"},
            {"indexed": False, "internalType": "address", "name": "target", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
            {"indexed": False, "internalType": "bytes", "name": "data", "type": "bytes"},
            {"indexed": False, "internalType": "bytes32", "name": "predecessor", "type": "bytes32"},
            {"indexed": False, "internalType": "uint256", "name": "delay", "type": "uint256"},
        ],
        "name": "CallScheduled",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "id", "type": "bytes32"},
            {"indexed": True, "internalType": "uint256", "name": "index", "type": "uint256"},
            {"indexed": False, "internalType": "address", "name": "target", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
            {"indexed": False, "internalType": "bytes", "name": "data", "type": "bytes"},
        ],
        "name": "CallExecuted",
        "type": "event",
    },
]


def check_timelocks(client, current_block):
    for name, address in TIMELOCKS.items():
        cache_key = f"{PROTOCOL}_{name}_last_block"
        last_block = int(get_last_value_for_key_from_file(cache_filename, cache_key))

        if last_block == 0:
            last_block = current_block - 100

        # Limit range to avoid RPC errors
        if current_block - last_block > 2000:
            last_block = current_block - 2000

        if last_block >= current_block:
            continue

        contract = client.get_contract(address, TIMELOCK_ABI)

        try:
            # Topic 0 hashes
            call_scheduled_topic = Web3.keccak(
                text="CallScheduled(bytes32,uint256,address,uint256,bytes,bytes32,uint256)"
            ).hex()
            call_executed_topic = Web3.keccak(text="CallExecuted(bytes32,uint256,address,uint256,bytes)").hex()

            events = client.eth.get_logs(
                {
                    "fromBlock": last_block + 1,
                    "toBlock": current_block,
                    "address": address,
                    "topics": [[call_scheduled_topic, call_executed_topic]],
                }
            )

            for event in events:
                topic0 = event["topics"][0].hex()

                if topic0 == call_scheduled_topic:
                    decoded = contract.events.CallScheduled().process_log(event)
                    event_name = "CallScheduled"
                    delay = f"\nDelay: {decoded['args'].get('delay')}s"
                else:
                    decoded = contract.events.CallExecuted().process_log(event)
                    event_name = "CallExecuted"
                    delay = ""

                args = decoded["args"]
                target = args.get("target")
                value = args.get("value")
                data = args.get("data").hex()

                msg = (
                    f"⏰ *Infinifi Timelock Action*\n\n"
                    f"Contract: {name}\n"
                    f"Event: {event_name}\n"
                    f"Target: {target}\n"
                    f"Value: {value}"
                    f"{delay}\n"
                    f"Data: {data[:10]}..."
                )
                send_telegram_message(msg, PROTOCOL)

            write_last_value_to_file(cache_filename, cache_key, current_block)
            print(f"Checked {name} from {last_block + 1} to {current_block}. Found {len(events)} events.")

        except Exception as e:
            print(f"Error checking {name}: {e}")


def check_deployer(client, current_block):
    cache_key = f"{PROTOCOL}_deployer_last_block"
    last_block = int(get_last_value_for_key_from_file(cache_filename, cache_key))

    if last_block == 0:
        last_block = current_block - 100

    # Limit range for deployer scanning since it's heavier
    if current_block - last_block > 1000:
        last_block = current_block - 1000

    if last_block >= current_block:
        return

    print(f"Checking deployer from {last_block + 1} to {current_block}...")

    chunk_size = 20
    for block_num in range(last_block + 1, current_block + 1, chunk_size):
        end = min(block_num + chunk_size - 1, current_block)

        try:
            batch = client.create_batch()
            for b in range(block_num, end + 1):
                batch.add(client.w3.eth.get_block(b, True))

            blocks = client.execute_batch(batch)

            for block in blocks:
                if not block or "transactions" not in block:
                    continue

                for tx in block["transactions"]:
                    if tx["from"] == DEPLOYER:
                        msg = (
                            f"👤 *Infinifi Deployer Action*\n\n"
                            f"Tx Hash: {tx['hash'].hex()}\n"
                            f"To: {tx.get('to')}\n"
                            f"Value: {tx.get('value')}\n"
                            f"Block: {block['number']}"
                        )
                        send_telegram_message(msg, PROTOCOL)

            # Update cache after each chunk to save progress
            write_last_value_to_file(cache_filename, cache_key, end)

        except Exception as e:
            print(f"Error checking deployer at block range {block_num}-{end}: {e}")
            break


def main():
    try:
        client = ChainManager.get_client(Chain.MAINNET)
    except Exception as e:
        print(f"Failed to get client: {e}")
        return

    current_block = client.eth.block_number
    print(f"Current block: {current_block}")

    check_timelocks(client, current_block)
    check_deployer(client, current_block)


if __name__ == "__main__":
    main()
