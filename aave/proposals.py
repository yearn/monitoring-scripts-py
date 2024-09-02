import requests, os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()


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


def is_submitted_in_last_hour(timestamp):
    now = datetime.now(timezone.utc)
    submission_date = datetime.fromtimestamp(timestamp, timezone.utc)
    one_hour_ago = now - timedelta(hours=1.2)
    return one_hour_ago <= submission_date <= now


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
    for proposal in proposals:
        timestamp = int(proposal['transactions']['active']['timestamp'])
        if not is_submitted_in_last_hour(timestamp):
            print(f"Skipping proposal: {proposal['id']} as it was submitted more than an hour ago.")
            continue

        date_time = datetime.fromtimestamp(timestamp)
        timestamp = date_time.strftime("%Y-%m-%d %H:%M:%S")
        message += (
            f"📕 Title: {proposal['proposalMetadata']['title']}\n"
            f"🆔 ID: {proposal['id']}\n"
            f"🕒 Submitted at: {timestamp}\n"
            f"🔗 Link to Proposal: {aave_url + proposal['id']}\n\n"
        )

    if not message:
        print("No proposals found in the last hour")
        return

    message = "🖋️ Aave Governance Proposals 🖋️\n" + message
    send_telegram_message(message, "AAVE")


if __name__ == "__main__":
    handle_governance_proposals()
