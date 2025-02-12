import requests
from utils.cache import get_last_queued_id_from_file, write_last_queued_id_to_file
from utils.telegram import send_telegram_message

PROTOCOL = "moonwell"


def fetch_moonwell_proposals():
    url = "https://ponder.moonwell.fi/graphql"
    query = """
    query {
        proposals(
            where: {
                proposalId_gt: 158 # the last reported proposal, fix for updating the cache
            }
            limit: 10,
            orderDirection: "desc",
            orderBy: "proposalId"
        ) {
            items {
                id
                description
                proposalId
                stateChanges(orderBy: "blockNumber") {
                    items {
                        newState
                        chainId
                    }
                }
            }
        }
    }
    """
    payload = {"query": query}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        base_proposals = []
        last_reported_id = get_last_queued_id_from_file(PROTOCOL)

        for proposal in data["data"]["proposals"]["items"]:
            state_changes = proposal["stateChanges"]["items"]
            for state_change in reversed(state_changes):
                if state_change["chainId"] == 8453:
                    match state_change["newState"]:
                        case "EXECUTED":
                            break  # skip executed proposals
                        case "QUEUED":
                            proposal_id = int(proposal["proposalId"])
                            if proposal_id > last_reported_id:
                                base_proposals.append(proposal)
                            else:
                                print("Proposal with id", proposal_id, "already sent")
                            break

        if not base_proposals:
            print("No new proposals found")
            return None

        moonwell_proposal_url = "https://moonwell.fi/governance/proposal/moonbeam?id="
        message = "🌙 Moonwell Governance Proposals 🌙\n"
        for proposal in base_proposals:
            proposal_id = proposal["proposalId"]
            proposal_url = moonwell_proposal_url + str(proposal_id)
            message += f"🔗 Link to Proposal: {proposal_url}\n"
            if proposal.get("description"):
                # there is no title so we use the first line of the description
                description = proposal["description"].split("\n")[0]
                if len(description) > 500:  # Still keep length limit for safety
                    description = description + "..."
                message += f"📗 Title: {description}\n\n"

        send_telegram_message(message, PROTOCOL)
        # write last sent queued proposal id to file
        write_last_queued_id_to_file(PROTOCOL, base_proposals[0]["proposalId"])
        return base_proposals

    except requests.exceptions.RequestException as e:
        # skip sending telegram message because tenderly alert is also set up for proposals
        error_message = f"Failed to fetch moonwell proposals: {e}"
        print(error_message)
        return None


if __name__ == "__main__":
    fetch_moonwell_proposals()
