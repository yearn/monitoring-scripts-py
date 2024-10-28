import requests, os

filename = os.getenv("FILENAME", "cache-id.txt")
PROTOCOL = "comp"
max_length_summary = 500


# TODO: extract these 2 functions to a common file
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


def extract_summary_from_description(description):
    # Extract the summary part
    summary_start = description.find("# Summary")
    if summary_start == -1:
        summary_start = description.find("## Proposal summary")
    motivation_start = description.find("# Motivation")
    if motivation_start == -1:
        motivation_start = description.find("## Proposal Action")
    summary = ""
    if summary_start != -1 and motivation_start != -1:
        summary_start = description.find("\n", summary_start)
        summary = description[summary_start:motivation_start].strip()
        summary = summary.replace("\n\n", "\n")
        # Truncate the summary if it exceeds max_length
        if len(summary) > max_length_summary:
            summary = summary[:max_length_summary].rsplit(" ", 1)[0] + "..."
    return summary


def fetch_and_filter_compound_proposals():
    url = "https://v3-api.compound.finance/governance/mainnet/all/proposals?page_size=10&page_number=1&with_detail=false"
    proposal_url = "https://compound.finance/governance/proposals/"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()
        queued_proposals = []
        last_reported_id = get_last_queued_id_from_file(PROTOCOL)

        # comp backend returns proposals in descending order by id
        for proposal in reversed(data.get("proposals", [])):
            states = proposal.get("states", [])
            for state in reversed(states):
                match state["state"]:
                    case "executed":
                        break  # skip executed proposals
                    case "queued":
                        proposal_id = int(proposal["id"])
                        if proposal_id > last_reported_id:
                            queued_proposals.append(proposal)
                        else:
                            print("Proposal with id", proposal_id, "already sent")
                        break  # exit loop after finding queued state

        if queued_proposals.__len__() == 0:
            print("No new proposals found")
            return None

        message = "🖋️ Compound Governance Proposals 🖋️\n"
        for proposal in queued_proposals:
            link = proposal_url + str(proposal["id"])
            message += (
                f"📗 Title: {proposal['title']}\n" f"🔗 Link to Proposal: {link}\n"
            )
            description = extract_summary_from_description(proposal["description"])
            if len(description) > 0:
                message += f"📝 Description: {description}\n\n"

        send_telegram_message(message, "COMP")
        # write last sent queued proposal id to file
        write_last_queued_id_to_file(PROTOCOL, queued_proposals[-1]["id"])
    except requests.RequestException as e:
        message = f"Failed to fetch compound proposals: {e}"
        send_telegram_message(message, "COMP")


def send_telegram_message(message, protocol):
    print(f"Sending telegram message:\n{message}")
    bot_token = os.getenv(f"TELEGRAM_BOT_TOKEN_{protocol.upper()}")
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{protocol.upper()}")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(
            f"Failed to send telegram message: {response.status_code} - {response.text}"
        )


if __name__ == "__main__":
    fetch_and_filter_compound_proposals()
