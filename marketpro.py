from market_data import get_market_pair_data
from scanner import calculate_smc_confluence
from bot import send_telegram_alert

WATCHLIST = [
    "BTC-USD",     # Bitcoin
    "ETH-USD",     # Ethereum
    "SOL-USD",     # Solana
    "BNB-USD",     # BNB
    "GC=F"         # Gold (XAUUSD)
]

def main():
    print(f"[INFO] Running MarketPro SMC Pro Scan for {len(WATCHLIST)} assets...")
    alerts_triggered = 0

    for symbol in WATCHLIST:
        df_ltf, df_htf = get_market_pair_data(symbol)
        if df_ltf.empty or df_htf.empty:
            continue

        result = calculate_smc_confluence(df_ltf, df_htf, symbol)
        if result.get("signal"):
            print(f"[ALERT] {result['type']} confirmed for {symbol}!")
            send_telegram_alert(result["message"])
            alerts_triggered += 1
        else:
            print(f"[DEBUG] {symbol}: No Signal ({result.get('score')})")

    print(f"[INFO] Scan complete. Total alerts sent: {alerts_triggered}")

if __name__ == "__main__":
    main()
