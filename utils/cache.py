import os

from dotenv import load_dotenv

load_dotenv()

# format of the data: "protocol:value"
cache_filename = os.getenv("CACHE_FILENAME", "cache-id.txt")
# format of the data: "address:nonce"
nonces_filename = os.getenv("NONCE_FILENAME", "nonces.txt")
# format of the data: "vault_address+market_id+type_value:cap_timestamp"
morpho_filename = os.getenv("MORPHO_FILENAME", "cache-id.txt")
# use the same cache file because it is run in the same hourly workflow


def get_last_queued_id_from_file(protocol):
    return get_last_value_for_key_from_file(cache_filename, protocol)


def write_last_queued_id_to_file(protocol, proposal_id):
    write_last_value_to_file(cache_filename, protocol, proposal_id)


def get_last_executed_nonce_from_file(safe_address):
    return get_last_value_for_key_from_file(nonces_filename, safe_address)


def write_last_executed_nonce_to_file(safe_address, nonce):
    write_last_value_to_file(nonces_filename, safe_address, nonce)


def get_last_executed_morpho_from_file(vault_address, market_id, value_type):
    return get_last_value_for_key_from_file(
        morpho_filename, morpho_key(vault_address, market_id, value_type)
    )


def write_last_executed_morpho_to_file(vault_address, market_id, value_type, value):
    write_last_value_to_file(
        morpho_filename, morpho_key(vault_address, market_id, value_type), value
    )


def morpho_key(vault_address, market_id, value_type):
    return vault_address + "+" + market_id + "+" + value_type


def get_last_value_for_key_from_file(filename, wanted_key):
    if not os.path.exists(filename):
        return 0
    else:
        with open(filename, "r") as f:
            # read line by line in format "key:value"
            lines = f.readlines()
            for line in lines:
                key, value = line.strip().split(":")
                if key == wanted_key:
                    return int(value)
    return 0


def write_last_value_to_file(filename, write_key, write_value):
    # check if the proposal ud is already in the file, then update the id else append
    if os.path.exists(filename):
        with open(filename, "r") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                key, _ = line.strip().split(":")
                if key == write_key:
                    lines[i] = f"{write_key}:{write_value}\n"
                    break
            else:
                lines.append(f"{write_key}:{write_value}\n")
        with open(filename, "w") as f:
            f.writelines(lines)
    else:
        lines = [f"{write_key}:{write_value}\n"]
        with open(filename, "w") as f:
            f.writelines(lines)
