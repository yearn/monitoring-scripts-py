"""
Tenderly monitoring script to verify that the expected number of alerts are present.
This script is run daily by Github actions to verify that alerts haven't changed.
"""

import hashlib
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()
TENDERLY_API_KEY = os.getenv("TENDERLY_API_KEY")
TENDERLY_API_URL = "https://api.tenderly.co/api/v1/account/yearn/project/sam/alerts"
EXPECTED_ALERT_HASH = "e7aaa5b96aaed6354011eb3f33a5c8c1e14cc13b0f1bae83dd231d64340d0e0c"


def get_response_hash(data: dict) -> str:
    """Generate a hash from the entire JSON response, sorted by alert ID."""
    # Sort alerts by ID for consistent hashing
    sorted_alerts = sorted(data.get("alerts", []), key=lambda x: x["id"])
    sorted_data = {"alerts": sorted_alerts}
    # Hash the entire JSON response
    json_str = json.dumps(sorted_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode()).hexdigest()


def main():
    headers = {"Accept": "application/json", "X-Access-Key": TENDERLY_API_KEY}
    response = requests.get(TENDERLY_API_URL, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get alerts: {response.status_code} - {response.text}")
    data = response.json()
    alerts = data.get("alerts", [])
    alert_count = len(alerts)
    response_hash = get_response_hash(data)
    if response_hash != EXPECTED_ALERT_HASH:
        raise Exception(
            f"❌ Check who has updated Tenderly alerts for SAM project, expected hash {EXPECTED_ALERT_HASH}, got {response_hash}"
        )
    print(f"✓ Verified {alert_count} alerts match expected count and response hash")


if __name__ == "__main__":
    main()
