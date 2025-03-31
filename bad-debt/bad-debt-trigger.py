import datetime
import locale
import os

import requests

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")


def get_data():
    url = os.environ["DATA_URL"]
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
    else:
        raise Exception(f"Failed to get data: {response.status_code} - {response.text}")

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

    if (
        threshold > 0 and total_bad_debt / 10**decimals > threshold
    ) or ratio_of_bad_debt > threshold_ratio:
        accounts = accounts_with_bad_debt(data)
        message += f"\n{accounts}"
        print("Sending telegram message...")
        print(message)
        bot_token = os.getenv("BAD_DEBT_TELEGRAM_TOKEN")
        chat_id = os.getenv("BAD_DEBT_TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id, "text": message}
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(
                f"Failed to send telegram message: {response.status_code} - {response.text}"
            )
    else:
        print("Thresholds not exceeded, no message sent")


def accounts_with_bad_debt(data) -> str:
    # Sort users by bad debt (most negative first)
    sorted_users = sorted(data["users"], key=lambda x: int(x["badDebt"]))
    # Get top 3 accounts
    top_3 = sorted_users[:3]
    decimals = int(data["decimals"])

    # Format the message
    message = "\nTop 3 accounts with bad debt:"
    for user in top_3:
        # Convert bad debt to USD with proper formatting using locale
        bad_debt_usd = abs(int(user["badDebt"])) / 10**decimals
        formatted_debt = locale.currency(bad_debt_usd, grouping=True)
        message += f"\n- {user['user']} = {formatted_debt}"

    return message


if __name__ == "__main__":
    get_data()
