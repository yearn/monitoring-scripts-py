import requests

def send_telegram_message(message):
    print(f"Sending message: {message}")

def check_positions():
    block_number = 20643640
    first = 100  # Number of items to fetch per request
    skip = 0     # Start with the first set of results

    while True:
        query = f"""
            fragment positionFields on Position {{
              marketAsset: market {{
                inputToken {{
                  id
                }}
              }}
              snapshots(first: 1, orderBy: blockNumber, orderDirection: desc) {{
                blockNumber
                hash
              }}
            }}

            query QueryPositions {{
              siloPositions(
                first: {first},
                skip: {skip},
                where: {{
                  dTokenBalance_gt: 0,
                  silo_: {{id_not_in: [""]}}
                }},
                orderBy: riskFactor,
                orderDirection: desc,
              ) {{
                id
                account {{
                  id
                }}
                silo {{
                  id
                  name
                  baseAsset {{
                    id
                  }}
                  bridgeAsset {{
                    id
                  }}
                  marketAssets: market {{
                    inputToken {{
                      id
                      symbol
                      decimals
                      lastPriceUSD
                    }}
                    liquidationThreshold
                  }}
                }}
                totalCollateralValue
                totalBorrowValue
                riskFactor
                riskScore
                collateralPositions: positions(where: {{ sTokenBalance_gt: 0 }}) {{
                  sTokenBalance
                  sToken {{
                    derivativeConversion
                  }}
                  ...positionFields
                }}
                collateralOnlyPositions: positions(where: {{ spTokenBalance_gt: 0 }}) {{
                  spTokenBalance
                  ...positionFields
                }}
                debtPositions: positions(where: {{ dTokenBalance_gt: 0 }}) {{
                  dTokenBalance
                  dToken {{
                    derivativeConversion
                  }}
                  ...positionFields
                }}
              }}
            }}
        """

        json_data = {
            "query": query,
            "operationName": "QueryPositions",
        }

        response = requests.post(
            "https://gateway-arbitrum.network.thegraph.com/api/8647ff8b021f8561ae98e65f752b4489/subgraphs/id/2ufoztRpybsgogPVW6j9NTn1JmBWFYPKbP7pAabizADU",
            json=json_data,
        )

        response_data = response.json()
        # print(response_data)

        # Check if there are any positions returned
        positions = response_data["data"]["siloPositions"]
        if not positions:
            break

        # Process each position
        for position in positions:
            risk_factor = float(position["riskFactor"])
            risk_score = float(position["riskScore"])

            if risk_factor > 0.95 and risk_score > 150_000:
                wallet_address = position["account"]["id"]
                input_token_symbol = position["silo"]["marketAssets"][0]["inputToken"][
                    "symbol"
                ]
                silo_name = position["silo"]["name"]
                total_borrow_value = position["totalBorrowValue"]

                message = f"""
High Risk Position Detected!
Wallet Address: {wallet_address}
Input Token Symbol: {input_token_symbol}
Silo Name: {silo_name}
Risk Factor: {risk_factor}
Risk Score: {risk_score}
Total Borrow Value: {total_borrow_value}
"""             
                print(message)
                # send_telegram_message(message)

        # Increment the skip value to fetch the next set of results
        skip += first

def main():
    print("Checking positions: ")
    check_positions()

if __name__ == "__main__":
    main()
