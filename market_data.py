import yfinance as yf
import pandas as pd

def get_market_pair_data(symbol: str):
    """
    LTF (15m) aur HTF (1h) dono fetch karta hai Higher Timeframe Confluence ke liye.
    """
    try:
        # 15m data for execution
        df_ltf = yf.download(symbol, period="5d", interval="15m", progress=False, auto_adjust=True)
        # 1h data for HTF EMA 50 Bias
        df_htf = yf.download(symbol, period="1mo", interval="1h", progress=False, auto_adjust=True)

        if df_ltf.empty or df_htf.empty:
            return pd.DataFrame(), pd.DataFrame()

        if isinstance(df_ltf.columns, pd.MultiIndex):
            df_ltf.columns = df_ltf.columns.get_level_values(0)
        if isinstance(df_htf.columns, pd.MultiIndex):
            df_htf.columns = df_htf.columns.get_level_values(0)

        return df_ltf.dropna(), df_htf.dropna()

    except Exception as e:
        print(f"[ERROR] Data fetch failed for {symbol}: {e}")
        return pd.DataFrame(), pd.DataFrame()
