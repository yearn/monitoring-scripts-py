import os
from dotenv import load_dotenv
from dune_client.client import DuneClient
from utils.telegram import send_telegram_message

load_dotenv()
dune = DuneClient(os.getenv("DUNE_API_KEY"))
PROTOCOL = "USD0"


def query_cf():
    query_result = dune.get_latest_result(3886520)
    newest_data = query_result.result.rows[0]
    collateral_factor = newest_data["collateral_factor"]
    if collateral_factor < 1.1:
        # Collateral factor has fallen below accept risk
        message = f"USD0 collateral factor is {collateral_factor}"
        send_telegram_message(message, PROTOCOL)


if __name__ == "__main__":
    query_cf()
