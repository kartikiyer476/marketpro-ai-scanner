import os
import time
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
]

INTERVAL_SECONDS = 60


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing.")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        },
        timeout=20,
    )

    response.raise_for_status()


def get_binance_price(symbol):
    url = "https://api.binance.com/api/v3/ticker/price"

    response = requests.get(
        url,
        params={"symbol": symbol},
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return float(data["price"])


def scan_market():
    print("MarketPro AI scanner started.")

    for symbol in SYMBOLS:
        try:
            price = get_binance_price(symbol)

            print(f"{symbol}: {price}")

        except Exception as error:
            print(f"{symbol} error: {error}")


def main():
    print("================================")
    print("MarketPro AI Scanner")
    print("BTC + ETH")
    print("================================")

    while True:
        try:
            scan_market()

        except Exception as error:
            print(f"Scanner error: {error}")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
