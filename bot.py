import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    message = (
        "🚀 MarketPro AI Scanner\n\n"
        "Telegram connection successful ✅\n"
        "Scanner setup is ready."
    )

    result = send_telegram(message)

    print("Telegram message sent successfully.")
    print(result)
