import requests, json, os
from dotenv import load_dotenv

load_dotenv()

def run_query(query, variables, subgraph_id):
    api_key = os.getenv("GRAPH_API_KEY")
    url = f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
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

def fetch_high_risk_silo_positions(subgraph_id):
    query = """
    query GetHighRiskSiloPositions($first: Int!, $skip: Int!) {
      siloPositions(
        first: $first,
        skip: $skip,
        where: { riskFactor_gt: "1" }
      ) {
        id
        totalBorrowValue
        totalCollateralValue
        totalLiquidationThresholdValue
        riskFactor
        silo {
          id
        }
      }
    }
    """

    first = 100  # Number of items to fetch per request
    high_risk_positions = []
    skip = 0
    iteration = 1

    while True:
        variables = {
            "first": first,
            "skip": skip
        }
        response = run_query(query, variables, subgraph_id)
        new_positions = response['data']['siloPositions']

        if not new_positions:
            break

        high_risk_positions.extend(new_positions)
        skip += len(new_positions)
        iteration += 1

    return high_risk_positions

# Function to calculate total bad debt
def calculate_bad_debt(positions):
    total_bad_debt = 0
    for position in positions:
        total_borrow_value = float(position["totalBorrowValue"])
        total_liquidation_threshold_value = float(position["totalLiquidationThresholdValue"])
        # that's probably not that bad debt... it's just late debt could be bad debt too
        bad_debt = total_borrow_value - total_liquidation_threshold_value
        total_bad_debt += bad_debt

    print(f"Total bad debt: {total_bad_debt}")
    return total_bad_debt

def process_silo(subgraph_id, network_name):
    positions = fetch_high_risk_silo_positions(subgraph_id)
    print(f"Processing {len(positions)} positions")

    # Calculate total bad debt
    total_bad_debts = calculate_bad_debt(positions)

    # define the threshold for bad debt
    if total_bad_debts > 0:
        # Base beep bop message
        message = "🚨 **Bad Debt Report** 🚨\n\n"
        message += f"⛓️ Silo on {network_name}\n"
        message += f"📈 Total Bad Debt: {total_bad_debts}\n"
        message += "----------------------\n"
        print(message)
        send_telegram_message(message)

def send_telegram_message(message):
    # Dynamically select the bot token and chat ID based on the protocol
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_SILO")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_SILO")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}
    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"Failed to send message: {response.status_code} - {response.text}")

def main():
    arbitrum_subgraph_id = "2ufoztRpybsgogPVW6j9NTn1JmBWFYPKbP7pAabizADU"
    mainnet_subgraph_id = "GTEyHhRmhRRJkQfrDWsapcZ8sBKAka4GFej6gn3BpJNq"

    print("Running for Mainnet...")
    process_silo(mainnet_subgraph_id, "Mainnet")

    print("Running for Arbitrum...")
    process_silo(arbitrum_subgraph_id, "Arbitrum")

if __name__ == "__main__":
    main()
