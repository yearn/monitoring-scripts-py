import datetime
import locale
import os

import requests

url = os.environ["DATA_URL"]
response = requests.get(url)
locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

if response.status_code == 200:
    data = response.json()
    total_bad_debt = int(data["total"]) * -1
    decimals = int(data["decimals"])
    updated = int(data["updated"])
    tvl = int(data["tvl"])
    deposits = int(data["deposits"])
    borrows = int(data["borrows"])

    # ratio of bad debt to total value locked
    ratio_of_bad_debt = round(total_bad_debt / tvl * 100, 4)
    date = datetime.datetime.fromtimestamp(updated)
    debt = locale.currency(total_bad_debt / 10**decimals, grouping=True)
    tvl = locale.currency(tvl / 10**decimals, grouping=True)
    deposits = locale.currency(deposits / 10**decimals, grouping=True)
    borrows = locale.currency(borrows / 10**decimals, grouping=True)
    threshold = int(os.getenv("DEBT_THRESHOLD", 0))
    threshold_ratio = float(os.getenv("DEBT_THRESHOLD_RATIO", 100))
    protocol = os.getenv("PROTOCOL", "")

    message = f"⚠️ {protocol} Bad Debt ratio: {ratio_of_bad_debt}% at {date} ⚠️\nDebt: {debt}\nTVL: {tvl}\nDeposits: {deposits}\nBorrows: {borrows}"
    print(message)

    if (threshold > 0 and total_bad_debt / 10**decimals > threshold) or ratio_of_bad_debt > threshold_ratio:
        print("Sending telegram message...")
        bot_token = os.getenv("BAD_DEBT_TELEGRAM_TOKEN")
        chat_id = os.getenv("BAD_DEBT_TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id, "text": message}
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to send telegram message: {response.status_code} - {response.text}")

else:
    print(f"Request failed with status code {response.status_code}")
    raise Exception(f"Request failed with status code {response.status_code}")
