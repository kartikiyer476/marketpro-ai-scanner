import requests


BINANCE_URL = "https://api.binance.com/api/v3/klines"


def get_candles(symbol="BTCUSDT", interval="15m", limit=100):
    response = requests.get(
        BINANCE_URL,
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
        timeout=20,
    )

    response.raise_for_status()

    raw = response.json()

    candles = []

    for item in raw:
        candles.append({
            "time": int(item[0]),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        })

    return candles


if __name__ == "__main__":
    candles = get_candles("BTCUSDT", "15m", 10)

    for candle in candles:
        print(candle)
