import requests, os
from datetime import datetime, timedelta

def fetch_and_filter_compound_proposals():
    url = "https://v3-api.compound.finance/governance/mainnet/all/proposals?page_size=5&page_number=1&with_detail=false"
    proposal_url = "https://compound.finance/governance/proposals/"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()

        now = datetime.now()
        # leave buffer of 12 minutes for GH actions
        one_hour_ago = now - timedelta(hours=1.2)
        queued_proposals = []

        for proposal in data.get('proposals', []):
            states = proposal.get('states', [])
            for state in reversed(states):
                match state['state']:
                    case 'executed':
                        break # skip executed proposals
                    case 'queued':
                        start_time = datetime.fromtimestamp(state['start_time'])
                        if one_hour_ago <= start_time <= now:
                            queued_proposals.append(proposal)

        if queued_proposals.__len__() == 0:
            print("No new proposals found")
            return None

        message = "🖋️ Compound Governance Proposals 🖋️\n"
        for proposal in queued_proposals:
            link = proposal_url + str(proposal['id'])
            message += (
                f"📗 Title: {proposal['title']}\n"
                f"🔗 Link to Proposal: {link}\n\n"
            )
        send_telegram_message(message, "COMP")
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
        raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")

if __name__ == "__main__":
    fetch_and_filter_compound_proposals()
