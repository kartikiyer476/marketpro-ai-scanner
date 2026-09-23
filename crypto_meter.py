import requests

def get_crypto_meter_data(symbol: str) -> dict:
    """
    Binance Institutional Order Flow Engine (Zero API Key Required)
    Tracks Live Taker Buy vs Taker Sell Volume in USD ($)
    """
    clean_symbol = symbol.replace("-USD", "USDT").replace("/", "").strip()
    
    # Gold (GC=F) is traditional, not on Binance spot
    if "GC=F" in symbol or "Gold" in symbol:
        return {
            "available": False,
            "display": "Traditional Commodity (Synthetic Volume Applied)",
            "buy_pct": 50.0,
            "sell_pct": 50.0,
            "net_flow_usd": 0.0,
            "status": "Neutral Macro Flow"
        }

    url = f"https://api.binance.com/api/v3/klines?symbol={clean_symbol}&interval=15m&limit=2"
    
    try:
        res = requests.get(url, timeout=8)
        if res.status_code != 200:
            return {"available": False, "buy_pct": 50.0, "sell_pct": 50.0}

        data = res.json()
        latest = data[-1]  # Latest 15m candle

        # Index 7: Total Quote Asset Volume ($)
        # Index 10: Taker Buy Quote Asset Volume ($)
        total_vol_usd = float(latest[7])
        buy_vol_usd = float(latest[10])
        sell_vol_usd = max(0.0, total_vol_usd - buy_vol_usd)

        if total_vol_usd <= 0:
            return {"available": False, "buy_pct": 50.0, "sell_pct": 50.0}

        buy_pct = (buy_vol_usd / total_vol_usd) * 100
        sell_pct = 100.0 - buy_pct
        net_delta_usd = buy_vol_usd - sell_vol_usd

        # Whale Flow Determination
        if buy_pct >= 62.0:
            whale_status = "🐋 HEAVY WHALE INFLOW (Aggressive Buying)"
        elif sell_pct >= 62.0:
            whale_status = "🚨 HEAVY WHALE DUMPING (Aggressive Selling)"
        elif buy_pct > 53.0:
            whale_status = "🟢 Moderate Bullish Accumulation"
        elif sell_pct > 53.0:
            whale_status = "🔴 Moderate Bearish Distribution"
        else:
            whale_status = "⚖️ Balanced / Consolidation Flow"

        return {
            "available": True,
            "total_usd": total_vol_usd,
            "buy_usd": buy_vol_usd,
            "sell_usd": sell_vol_usd,
            "buy_pct": round(buy_pct, 1),
            "sell_pct": round(sell_pct, 1),
            "net_flow_usd": net_delta_usd,
            "status": whale_status
        }

    except Exception as e:
        return {"available": False, "buy_pct": 50.0, "sell_pct": 50.0}
