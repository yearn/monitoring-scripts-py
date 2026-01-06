"""
Tenderly monitoring script to verify that the expected number of alerts are present.
This script is run daily by Github actions to verify that the expected number of alerts are present.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()
TENDERLY_API_KEY = os.getenv("TENDERLY_API_KEY")
TENDERLY_API_URL = "https://api.tenderly.co/api/v1/account/yearn/project/sam/alerts"
EXPECTED_ALERT_COUNT = 29


def main():
    headers = {"Accept": "application/json", "X-Access-Key": TENDERLY_API_KEY}
    response = requests.get(TENDERLY_API_URL, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get alerts: {response.status_code} - {response.text}")

    data = response.json()
    alert_count = len(data.get("alerts", []))
    if alert_count != EXPECTED_ALERT_COUNT:
        raise Exception(f"Alert count mismatch: expected {EXPECTED_ALERT_COUNT}, got {alert_count}")
    print(f"✓ Verified {alert_count} alerts match expected count")


if __name__ == "__main__":
    main()
