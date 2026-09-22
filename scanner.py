
import time
import requests

from market_data import get_candles
from marketpro import score

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT"
]

TIMEFRAME = "15m"
CHECK_INTERVAL = 60

last_alerts = {}


def send_telegram(message):
    import os

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": chat,
            "text": message
        },
        timeout=20
    )


def should_alert(symbol, result):
    key = f"{symbol}_{result['signal']}_{result['bull']}_{result['bear']}"

    if last_alerts.get(symbol) == key:
        return False

    last_alerts[symbol] = key
    return True


def build_message(symbol, result, price):

    return (
        f"🚨 MARKETPRO AI\n\n"
        f"Symbol: {symbol}\n"
        f"TF: {TIMEFRAME}\n\n"
        f"Signal: {result['signal']}\n"
        f"Bull Score: {result['bull']}/10\n"
        f"Bear Score: {result['bear']}/10\n\n"
        f"Price: {price}\n"
        f"Structure: {result['structure']}\n\n"
        f"Fib 0.5: {result['fib']['50']:.2f}\n"
        f"Fib 0.618: {result['fib']['618']:.2f}"
    )


def process_symbol(symbol):

    candles = get_candles(symbol, TIMEFRAME, 200)

    result = score(candles)

    if result is None:
        return

    price = candles[-1]["close"]

    print(symbol, result)

    alert = False

    if result["signal"] in ["LONG", "SHORT"]:
        alert = True

    elif result["bull"] >= 7:
        alert = True

    elif result["bear"] >= 7:
        alert = True

    elif result["bull"] >= 6:
        alert = True

    elif result["bear"] >= 6:
        alert = True

    if alert and should_alert(symbol, result):
        send_telegram(build_message(symbol, result, price))


def main():

    print("MarketPro AI Scanner Started")

    while True:

        for symbol in SYMBOLS:

            try:
                process_symbol(symbol)

            except Exception as error:
                print(symbol, error)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    scan_market()
    print("Scan completed.")

