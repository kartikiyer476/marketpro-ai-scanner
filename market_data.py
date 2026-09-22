import yfinance as yf
import pandas as pd

def get_ohlcv(symbol: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
    """
    Yahoo Finance se candle data fetch karta hai aur structure clean karta hai.
    """
    try:
        df = yf.download(
            tickers=symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True
        )
        
        if df.empty or len(df) < 10:
            print(f"[WARN] Data available nahi hai for: {symbol}")
            return pd.DataFrame()

        # yfinance multi-index columns clean karna
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()
        return df

    except Exception as e:
        print(f"[ERROR] Data fetch error ({symbol}): {e}")
        return pd.DataFrame()
