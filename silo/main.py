import requests
import time


def send_telegram_message(message):
    print(f"Sending message: {message}")

def check_positions():
    block_number = 20643640

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
            first: 100,
            skip: 0,
            where: {{
              dTokenBalance_gt: 0,
              silo_: {{id_not_in: [""]}}
            }},
            orderBy: riskFactor,
            orderDirection: desc,
            block: {{ number_gte: 19112526 }}
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
        "https://gateway.thegraph.com/api/41d8e9d9c63d206f22b98602980156de/subgraphs/id/81ER342viJd3oRvPf28M7GwsnToa1RVWDNLnTr1eBciC",
        json=json_data,
    )

    # https://gateway.thegraph.com/api/41d8e9d9c63d206f22b98602980156de/subgraphs/id/81ER342viJd3oRvPf28M7GwsnToa1RVWDNLnTr1eBciC

    response_data = response.json()

    for position in response_data["data"]["siloPositions"]:
        risk_factor = float(position["riskFactor"])
        risk_score = float(position["riskScore"])

        if risk_factor > 0.95 and risk_score > 80_00:
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

def main():
    print("Checking positions: ")
    check_positions()

if __name__ == "__main__":
    main()
