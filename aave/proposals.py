import os
from datetime import datetime

import requests

from utils.cache import get_last_queued_id_from_file, write_last_queued_id_to_file
from utils.telegram import send_telegram_message

PROTOCOL = "aave"


def run_query(query, variables):
    api_key = os.getenv("GRAPH_API_KEY")
    subgraph_id = "A7QMszgomC9cnnfpAcqZVLr2DffvkGNfimD8iUSMiurK"
    url = f"https://gateway-arbitrum.network.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    headers = {"Content-Type": "application/json"}
    request_body = {"query": query, "variables": variables}
    response = requests.post(url, json=request_body, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")


def fetch_queued_proposals(last_reported_id: int):
    # state: 3 is queued state: https://github.com/bgd-labs/aave-governance-v3/blob/0c14d60ac89d7a9f79d0a1f77de5c99c3ba1201f/src/interfaces/IGovernanceCore.sol#L75
    # queued state is transferred to active state when it's executed, few seconds later so we need to check state 4
    query = """
        query($lastId: Int!) {
            proposals(where:{state:4, proposalId_gt:$lastId}) {
                proposalId
                proposalMetadata{
                    title
                }
                transactions{
                    executed{
                        timestamp
                    }
                }
            }
        }
    """

    # get only last 10 proposals
    variables = {"lastId": last_reported_id}
    response = run_query(query, variables)
    if "errors" in response:
        # NOTE: not raising error because the graph is not reliable. We have Tenderly alerts for this also
        print(f"Error fetching proposals: {response['errors']}")
        return []

    proposals = response["data"]["proposals"]
    return proposals


def handle_governance_proposals():
    last_sent_id = get_last_queued_id_from_file(PROTOCOL)
    proposals = fetch_queued_proposals(last_sent_id)
    if not proposals:
        print("No proposals found")
        return

    aave_url = "https://app.aave.com/governance/v3/proposal/?proposalId="
    message = ""
    for proposal in proposals:
        timestamp = int(proposal["transactions"]["executed"]["timestamp"])
        proposal_id = int(proposal["proposalId"])
        if proposal_id <= last_sent_id:
            print(f"Proposal: {proposal['proposalId']} already reported")
            continue

        date_time = datetime.fromtimestamp(timestamp)
        timestamp = date_time.strftime("%Y-%m-%d %H:%M:%S")
        message += (
            f"📕 Title: {proposal['proposalMetadata']['title']}\n"
            f"🆔 ID: {proposal['proposalId']}\n"
            f"🕒 Queued at: {timestamp}\n"
            f"🔗 Link to Proposal: {aave_url + proposal['proposalId']}\n\n"
        )

    if not message:
        print("No proposals found in the last hour")
        return

    message = "🖋️ Queued Aave Governance Proposals 🖋️\n" + message
    send_telegram_message(message, PROTOCOL)
    write_last_queued_id_to_file(PROTOCOL, proposals[-1]["proposalId"])


if __name__ == "__main__":
    handle_governance_proposals()
