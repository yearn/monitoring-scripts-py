import requests
import os
from dotenv import load_dotenv

load_dotenv()

# GraphQL query for all Silo's
query = """
{
  siloPositions {
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

arbitrum_subgraph_id = "2ufoztRpybsgogPVW6j9NTn1JmBWFYPKbP7pAabizADU"
mainnet_subgraph_id = "GTEyHhRmhRRJkQfrDWsapcZ8sBKAka4GFej6gn3BpJNq"

def run_query(query, subgraph_id):
    api_key = os.getenv("GRAPH_API_KEY")
    url = f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")

# Function to calculate total bad debt
def calculate_bad_debt(positions):
    total_deposits = 0
    total_borrows = 0
    total_bad_debt = 0
    i = 0 # just wondering how many iterations
    for position in positions:
        total_deposits += float(position["totalCollateralValue"])
        total_borrows += float(position["totalBorrowValue"])
        risk_factor = float(position["riskFactor"])

        if risk_factor > 1:
            total_borrow_value = float(position["totalBorrowValue"])
            total_liquidation_threshold_value = float(position["totalLiquidationThresholdValue"])
            # thats probably not that bad debt... it's just late debt could be bad debt too
            bad_debt = total_borrow_value - total_liquidation_threshold_value
            total_bad_debt += bad_debt

    tvl = total_deposits - total_borrows
    print(f"Total bad debt: {total_bad_debt}")
    print(f"Total TVL: {tvl}")
    return total_bad_debt, tvl

def process_silo(subgraph_id, network_name):
    result = run_query(query, subgraph_id)

    # Get the position
    positions = result.get('data', {}).get('siloPositions', [])
    print(f"Processing {len(positions)} positions")

    # Calculate total bad debt
    total_bad_debts, tvl = calculate_bad_debt(positions)
    debt_ratio = round(total_bad_debts / tvl * 100, 4)
    # Update this to your desired threshold
    threshold_ratio = 0.1 # 0.1% threshold

    if debt_ratio > threshold_ratio:
        # Base beep bop message
        message = "🚨 **Bad Debt Report** 🚨\n\n"
        message += f"🅿️ Protocol: Silo on {network_name}\n"
        message += f"📊 Bad Debt Ratio: {debt_ratio}%\n"
        message += f"📈 Total Bad Debt: {total_bad_debts}\n"
        message += f"💰 TVL: {tvl}\n"
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
    print("Running for Mainnet...")
    process_silo(mainnet_subgraph_id, "Mainnet")

    print("Running for Arbitrum...")
    process_silo(arbitrum_subgraph_id, "Arbitrum")

if __name__ == "__main__":
    main()
