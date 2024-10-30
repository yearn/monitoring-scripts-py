import os
from dotenv import load_dotenv

load_dotenv()

filename = os.getenv("FILENAME", "cache-id.txt")


def get_last_queued_id_from_file(protocol):
    if not os.path.exists(filename):
        return 0
    else:
        with open(filename, "r") as f:
            # read line by line in format "protocol:proposal_id"
            lines = f.readlines()
            for line in lines:
                protocol_name, proposal_id = line.strip().split(":")
                if protocol_name == protocol:
                    return int(proposal_id)
    return 0


def write_last_queued_id_to_file(protocol, last_id):
    # check if the proposal ud is already in the file, then update the id else append
    if os.path.exists(filename):
        with open(filename, "r") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                protocol_name, _ = line.strip().split(":")
                if protocol_name == protocol:
                    lines[i] = f"{protocol}:{last_id}\n"
                    break
            else:
                lines.append(f"{protocol}:{last_id}\n")
        with open(filename, "w") as f:
            f.writelines(lines)
    else:
        lines = [f"{protocol}:{last_id}\n"]
        with open(filename, "w") as f:
            f.writelines(lines)
