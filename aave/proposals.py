import requests, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

filename = os.getenv('FILENAME', 'cache-id.txt')
PROTOCOL = "aave"

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


def run_query(query, variables):
    api_key = os.getenv("GRAPH_API_KEY")
    subgraph_id = "A7QMszgomC9cnnfpAcqZVLr2DffvkGNfimD8iUSMiurK"
    url = f"https://gateway-arbitrum.network.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    headers = {"Content-Type": "application/json"}
    request_body = {
        'query': query,
        'variables': variables
    }
    response = requests.post(url, json=request_body, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")


def fetch_queued_proposals():
    # state: 3 is queued state: https://github.com/bgd-labs/aave-governance-v3/blob/0c14d60ac89d7a9f79d0a1f77de5c99c3ba1201f/src/interfaces/IGovernanceCore.sol#L75
    query = """
        {
            proposals(where:{state:3}) {
                id
                proposalMetadata{
                    title
                }
                transactions{
                    queued{
                        timestamp
                    }
                }
            }
        }
    """

    # get only last 10 proposals
    variables = {
        "first": 10,
        "skip": 0
    }
    response = run_query(query, variables)
    if 'errors' in response:
        # don't send message or raise exception because graph is reliable
        raise Exception(f"Query failed: {response['errors']}")

    proposals = response['data']['proposals']
    return proposals


def send_telegram_message(message, protocol):
    print(f"Sending telegram message:\n{message}")
    bot_token = os.getenv(f"TELEGRAM_BOT_TOKEN_{protocol.upper()}")
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{protocol.upper()}")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")


def handle_governance_proposals():
    proposals = fetch_queued_proposals()
    if not proposals:
        print("No proposals found")
        return

    aave_url = "https://app.aave.com/governance/v3/proposal/?proposalId="
    message = ""
    last_sent_id = get_last_queued_id_from_file(PROTOCOL)
    for proposal in proposals:
        timestamp = int(proposal['transactions']['active']['timestamp'])
        proposal_id = int(proposal['id'])
        if proposal_id <= last_sent_id:
            print(f"Proposal: {proposal['id']} already reported")
            continue

        date_time = datetime.fromtimestamp(timestamp)
        timestamp = date_time.strftime("%Y-%m-%d %H:%M:%S")
        message += (
            f"📕 Title: {proposal['proposalMetadata']['title']}\n"
            f"🆔 ID: {proposal['id']}\n"
            f"🕒 Queued at: {timestamp}\n"
            f"🔗 Link to Proposal: {aave_url + proposal['id']}\n\n"
        )

    if not message:
        print("No proposals found in the last hour")
        return

    message = "🖋️ Queued Aave Governance Proposals 🖋️\n" + message
    send_telegram_message(message, "AAVE")
    write_last_queued_id_to_file(PROTOCOL, proposals[-1]['id'])

if __name__ == "__main__":
    handle_governance_proposals()
