import os, requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram_message(message, protocol, disable_notification=False):
    print(f"Sending telegram message:\n{message}")
    max_message_length = 4096
    if len(message) > max_message_length:
        message = message[: max_message_length - 3] + "..."

    bot_token = os.getenv(f"TELEGRAM_BOT_TOKEN_{protocol.upper()}")
    chat_id = os.getenv(f"TELEGRAM_CHAT_ID_{protocol.upper()}")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
        "disable_notification": disable_notification,
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(
            f"Failed to send telegram message: {response.status_code} - {response.text}"
        )
