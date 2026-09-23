import numpy as np
import pandas as pd
import pandas_ta as ta

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    """
    MarketPro SMC Confluence Engine - Professional Investor Report Format
    """
    if df_ltf.empty or len(df_ltf) < 45:
        return {"signal": False, "score": "Data Insufficient"}

    df = df_ltf.copy()

    # 1. Inputs & Parameters
    pivot_len = 5
    atr_len = 14
    disp_atr_mult = 1.15
    disp_body_pct = 0.55
    vol_len = 20
    vol_mult = 1.3
    fvg_min_atr = 0.08
    min_score = 6

    # 2. Indicators Calculation
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=atr_len)
    df['VolMA'] = df['Volume'].rolling(window=vol_len).mean()
    df['HighVolume'] = df['Volume'] > (df['VolMA'] * vol_mult)

    candle_range = df['High'] - df['Low']
    body = (df['Close'] - df['Open']).abs()
    body_pct = np.where(candle_range > 0, body / candle_range, 0.0)

    df['BullDisp'] = (df['Close'] > df['Open']) & (candle_range >= df['ATR'] * disp_atr_mult) & (body_pct >= disp_body_pct)
    df['BearDisp'] = (df['Close'] < df['Open']) & (candle_range >= df['ATR'] * disp_atr_mult) & (body_pct >= disp_body_pct)

    # VWAP
    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    if df['VWAP'].isna().all():
        hlc3 = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (hlc3 * df['Volume']).cumsum() / df['Volume'].cumsum()

    # 3. Swings & Structure Tracking
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)

    last_swing_high = None
    last_swing_low = None
    last_high_bar = None
    last_low_bar = None
    structure_bias = 0

    bull_break_bars = []
    bear_break_bars = []
    bull_sweep_bars = []
    bear_sweep_bars = []

    for i in range(pivot_len, n - pivot_len):
        is_ph = all(highs[i - pivot_len] >= highs[i - pivot_len - j] and highs[i - pivot_len] >= highs[i - pivot_len + j] for j in range(1, pivot_len + 1))
        if is_ph:
            last_swing_high = highs[i - pivot_len]
            last_high_bar = i - pivot_len

        is_pl = all(lows[i - pivot_len] <= lows[i - pivot_len - j] and lows[i - pivot_len] <= lows[i - pivot_len + j] for j in range(1, pivot_len + 1))
        if is_pl:
            last_swing_low = lows[i - pivot_len]
            last_low_bar = i - pivot_len

        close_cur = df['Close'].iloc[i]
        close_prev = df['Close'].iloc[i - 1]

        if last_swing_high and close_cur > last_swing_high and close_prev <= last_swing_high:
            structure_bias = 1
            bull_break_bars.append(i)

        if last_swing_low and close_cur < last_swing_low and close_prev >= last_swing_low:
            structure_bias = -1
            bear_break_bars.append(i)

        if last_swing_high and df['High'].iloc[i] > last_swing_high and close_cur < last_swing_high:
            bear_sweep_bars.append(i)

        if last_swing_low and df['Low'].iloc[i] < last_swing_low and close_cur > last_swing_low:
            bull_sweep_bars.append(i)

    # 4. Confluence Scoring & Reason Tracking
    current_idx = n - 1
    bull_fvg = ((df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) >= df['ATR'] * fvg_min_atr)).iloc[-6:].any()
    bear_fvg = ((df['High'] < df['Low'].shift(2)) & ((df['Low'].shift(2) - df['High']) >= df['ATR'] * fvg_min_atr)).iloc[-6:].any()

    latest_close = df['Close'].iloc[-1]
    latest_vwap = df['VWAP'].iloc[-1] if not pd.isna(df['VWAP'].iloc[-1]) else latest_close
    latest_atr = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else 0

    # HTF 1H Bias
    htf_bull, htf_bear = True, True
    if not df_htf.empty and len(df_htf) >= 20:
        df_htf['EMA50'] = ta.ema(df_htf['Close'], length=min(50, len(df_htf) - 1))
        htf_bull = df_htf['Close'].iloc[-1] >= df_htf['EMA50'].iloc[-1]
        htf_bear = df_htf['Close'].iloc[-1] <= df_htf['EMA50'].iloc[-1]

    bull_reasons = []
    bear_reasons = []

    # 1. Structure
    if structure_bias == 1:
        bull_reasons.append("Structure: Bullish Trend (Higher Highs / Lows)")
    elif structure_bias == -1:
        bear_reasons.append("Structure: Bearish Trend (Lower Lows / Highs)")

    # 2. Sweeps
    if any(current_idx - b <= 8 for b in bull_sweep_bars):
        bull_reasons.append("Liquidity: Sell-Side Liquidity (SSL) Swept")
    if any(current_idx - b <= 8 for b in bear_sweep_bars):
        bear_reasons.append("Liquidity: Buy-Side Liquidity (BSL) Swept")

    # 3. BOS / MSS
    if any(current_idx - b <= 8 for b in bull_break_bars):
        bull_reasons.append("Breakout: Confirmed Bullish BOS / MSS")
    if any(current_idx - b <= 8 for b in bear_break_bars):
        bear_reasons.append("Breakout: Confirmed Bearish BOS / MSS")

    # 4. Displacement
    if df['BullDisp'].iloc[-4:].any():
        bull_reasons.append("Displacement: Strong Buying Pressure (Institutional Candle)")
    if df['BearDisp'].iloc[-4:].any():
        bear_reasons.append("Displacement: Strong Selling Pressure (Institutional Candle)")

    # 5. Volume
    if df['HighVolume'].iloc[-4:].any():
        bull_reasons.append("Volume: High Volume Surge (>1.3x 20-MA)")
        bear_reasons.append("Volume: High Volume Surge (>1.3x 20-MA)")

    # 6. FVG
    if bull_fvg:
        bull_reasons.append("Fair Value Gap: Active Bullish Imbalance / FVG")
    if bear_fvg:
        bear_reasons.append("Fair Value Gap: Active Bearish Imbalance / FVG")

    # 7. VWAP
    if latest_close > latest_vwap:
        bull_reasons.append("VWAP: Price Trading Above Session VWAP")
    else:
        bear_reasons.append("VWAP: Price Trading Below Session VWAP")

    # 8. HTF Bias
    if htf_bull:
        bull_reasons.append("HTF Bias: Aligned Bullish (Above 1H 50 EMA)")
    if htf_bear:
        bear_reasons.append("HTF Bias: Aligned Bearish (Below 1H 50 EMA)")

    # 9. Session (Crypto 24/7)
    bull_reasons.append("Session: Active Market Liquidity")
    bear_reasons.append("Session: Active Market Liquidity")

    # 10. Key S/R
    if last_swing_low and abs(latest_close - last_swing_low) <= latest_atr * 1.5:
        bull_reasons.append("Level: Reacting off Major Support Zone")
    if last_swing_high and abs(latest_close - last_swing_high) <= latest_atr * 1.5:
        bear_reasons.append("Level: Reacting off Major Resistance Zone")

    bull_score = len(bull_reasons)
    bear_score = len(bear_reasons)

    long_trigger = (bull_score >= min_score) and (bull_score > bear_score)
    short_trigger = (bear_score >= min_score) and (bear_score > bull_score)

    # Auto Fib OTE Range & Invalidation
    ote_str = "N/A"
    invalidation_level = "Structural Pivot"
    if last_swing_high and last_swing_low:
        dist = abs(last_swing_high - last_swing_low)
        if last_high_bar and last_low_bar and last_high_bar > last_low_bar:
            f1, f2 = last_swing_high - dist * 0.618, last_swing_high - dist * 0.786
            ote_str = f"${min(f1, f2):,.2f} -${max(f1, f2):,.2f}"
            invalidation_level = f"${last_swing_low:,.2f}"
        elif last_high_bar and last_low_bar:
            f1, f2 = last_swing_low + dist * 0.618, last_swing_low + dist * 0.786
            ote_str = f"${min(f1, f2):,.2f} -${max(f1, f2):,.2f}"
            invalidation_level = f"${last_swing_high:,.2f}"

    clean_symbol = symbol.replace("-USD", "/USDT").replace("=F", " Gold Spot")

    # 5. Professional Investor Trade Report Message
    if long_trigger:
        reasons_formatted = "\n".join([f"  • {r}" for r in bull_reasons[:6]])
        msg = (
            f"⚡ *MARKETPRO AI | INSTITUTIONAL TRADE ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{clean_symbol}` (15m TF)\n"
            f"🎯 *Bias / Action:* *BUY / LONG* 🟢\n"
            f"💵 *Current Price:* `${latest_close:,.2f}`\n"
            f"📊 *Confluence Score:* `{bull_score}/10` (High Probability)\n\n"
            f"🔍 *Why This Setup Triggered:*\n"
            f"{reasons_formatted}\n\n"
            f"📐 *Key Trade Levels:*\n"
            f"• *Optimal Entry (OTE 61.8%-78.6%):* `{ote_str}`\n"
            f"• *Structural Invalidation (SL Zone):* `< {invalidation_level}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 _Analyst Note: Smart money accumulation confirmed. Wait for retest into OTE or enter with managed risk._"
        )
        return {"signal": True, "type": "LONG", "message": msg}

    if short_trigger:
        reasons_formatted = "\n".join([f"  • {r}" for r in bear_reasons[:6]])
        msg = (
            f"⚡ *MARKETPRO AI | INSTITUTIONAL TRADE ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{clean_symbol}` (15m TF)\n"
            f"🎯 *Bias / Action:* *SELL / SHORT* 🔴\n"
            f"💵 *Current Price:* `${latest_close:,.2f}`\n"
            f"📊 *Confluence Score:* `{bear_score}/10` (High Probability)\n\n"
            f"🔍 *Why This Setup Triggered:*\n"
            f"{reasons_formatted}\n\n"
            f"📐 *Key Trade Levels:*\n"
            f"• *Optimal Entry (OTE 61.8%-78.6%):* `{ote_str}`\n"
            f"• *Structural Invalidation (SL Zone):* `> {invalidation_level}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 _Analyst Note: Buy-side liquidity swept and institutional distribution active. Target recent swing lows._"
        )
        return {"signal": True, "type": "SHORT", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
