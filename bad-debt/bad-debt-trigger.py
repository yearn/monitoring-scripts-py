import os, requests, datetime, locale
import asyncio, telegram

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
    ratio_of_bad_debt = round(total_bad_debt / tvl * 100, 2)
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

    if (
        threshold > 0 and total_bad_debt / 10**decimals > threshold
    ) or ratio_of_bad_debt > threshold_ratio:
        bot = telegram.Bot(token=os.environ["BAD_DEBT_TELEGRAM_TOKEN"])
        chat_ids = os.environ["BAD_DEBT_TELEGRAM_CHAT_ID"].split(",")
        print(f"Sending Telegram message")
        for chat_id in chat_ids:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(bot.send_message(chat_id=chat_id, text=message))
else:
    print(f"Request failed with status code {response.status_code}")
