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
    total_bad_debts = {}
    i = 0 # just wondering how many iterations
    for position in positions:
        i = i + 1
        risk_factor = float(position["riskFactor"])

        if risk_factor > 1:
            total_borrow_value = float(position["totalBorrowValue"])
            total_liquidation_threshold_value = float(position["totalLiquidationThresholdValue"])
            # thats probably not that bad debt.. it's just late debt could be bad debt too
            bad_debt = total_borrow_value - total_liquidation_threshold_value 
            
            silo_id = position["silo"]["id"]
            if silo_id not in total_bad_debts:
                total_bad_debts[silo_id] = 0
            
            total_bad_debts[silo_id] += bad_debt
    
    print(f"Iterations: {i}")
        
    return total_bad_debts

def process_silo(subgraph_id, ):
    result = run_query(query, subgraph_id)
    
    # Get the position
    positions = result.get('data', {}).get('siloPositions', [])
    
    # Calculate total bad debt
    total_bad_debts = calculate_bad_debt(positions)
    
    # Base beep bop message
    message = "🚨 **Bad Debt Report** 🚨\n\n"
    
    # Flag to check if we have any bad debts to report, when we have bad debt we print
    has_bad_debt = False
    
    for silo_id, bad_debt in total_bad_debts.items():
        if bad_debt > 0:
            has_bad_debt = True
            message += f"Silo ID: {silo_id}\n"
            message += f"💰 Total Bad Debt: {bad_debt}\n"
            message += "----------------------\n"
    
    # Print the final message only if there's bad debt
    if has_bad_debt:
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
    process_silo(mainnet_subgraph_id)

    print("Running for Arbitrum...")
    process_silo(arbitrum_subgraph_id)

if __name__ == "__main__":
    main()

