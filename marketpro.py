from market_data import get_ohlcv
from scanner import run_strategy_scan
from bot import send_telegram_alert

# Watchlist: Yahan aap apne stocks ya indices add kar sakte hain
WATCHLIST = [
    "^NSEI",         # Nifty 50
    "^NSEBANK",      # Bank Nifty
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS"
]

TIMEFRAME = "15m"
DATA_PERIOD = "5d"

def main():
    print(f"[INFO] MarketPro scan started for {len(WATCHLIST)} symbols...")
    triggered_count = 0

    for symbol in WATCHLIST:
        df = get_ohlcv(symbol=symbol, interval=TIMEFRAME, period=DATA_PERIOD)
        if df.empty:
            continue

        result = run_strategy_scan(df, symbol)
        if result.get("signal"):
            print(f"[ALERT] Trigger matched for {symbol} ({result['type']})")
            send_telegram_alert(result["message"])
            triggered_count += 1

    print(f"[INFO] Scan complete. Total alerts sent: {triggered_count}")

if __name__ == "__main__":
    main()
