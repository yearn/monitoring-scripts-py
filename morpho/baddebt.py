import requests

# Only example how to get bad debt for a specific market

API_URL = "https://blue-api.morpho.org/graphql"

variables = {
    "wanted_markets": [
        "0xb48bb53f0f2690c71e8813f2dc7ed6fca9ac4b0ace3faa37b4a8e5ece38fa1a2"
    ],
}

query_bad_debt = """
query($wanted_markets: [String!]!) {
  markets(where: {uniqueKey_in: $wanted_markets}) {
    items {
      uniqueKey
      lltv
      oracleAddress
      irmAddress
      loanAsset {
        address
        symbol
        decimals
      }
      collateralAsset {
        address
        symbol
        decimals
      }
      state {
        borrowApy
        borrowAssets
        borrowAssetsUsd
        supplyApy
        supplyAssets
        supplyAssetsUsd
        fee
        utilization
      }
      badDebt {
        underlying
        usd
      }
    }
  }
}
"""

json_data = {
    "query": query_bad_debt,
    "variables": variables,
}

response = requests.post(
    API_URL,
    json=json_data,
)

print(response.json())
