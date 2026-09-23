import numpy as np
import pandas as pd
import pandas_ta as ta

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    """
    MarketPro SMC Confluence Engine - 6/10 Direct Alert Mode
    """
    if df_ltf.empty or len(df_ltf) < 40:
        return {"signal": False, "score": "Data Insufficient"}

    df = df_ltf.copy()

    # 1. Core Parameters
    pivot_len = 5
    atr_len = 14
    disp_atr_mult = 1.1      # Thoda responsive banaya taaki displacement pakad sake
    disp_body_pct = 0.50     # 50% candle body
    vol_len = 20
    vol_mult = 1.2
    fvg_min_atr = 0.08
    min_score = 6            # 🚨 Seedha 6/10 par alert

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

    # 3. Swings & BOS/MSS Tracking
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
        # Pivot High
        is_ph = all(highs[i - pivot_len] >= highs[i - pivot_len - j] and highs[i - pivot_len] >= highs[i - pivot_len + j] for j in range(1, pivot_len + 1))
        if is_ph:
            last_swing_high = highs[i - pivot_len]
            last_high_bar = i - pivot_len

        # Pivot Low
        is_pl = all(lows[i - pivot_len] <= lows[i - pivot_len - j] and lows[i - pivot_len] <= lows[i - pivot_len + j] for j in range(1, pivot_len + 1))
        if is_pl:
            last_swing_low = lows[i - pivot_len]
            last_low_bar = i - pivot_len

        close_cur = df['Close'].iloc[i]
        close_prev = df['Close'].iloc[i - 1]

        # Breakouts
        if last_swing_high and close_cur > last_swing_high and close_prev <= last_swing_high:
            structure_bias = 1
            bull_break_bars.append(i)

        if last_swing_low and close_cur < last_swing_low and close_prev >= last_swing_low:
            structure_bias = -1
            bear_break_bars.append(i)

        # Sweeps
        if last_swing_high and df['High'].iloc[i] > last_swing_high and close_cur < last_swing_high:
            bear_sweep_bars.append(i)

        if last_swing_low and df['Low'].iloc[i] < last_swing_low and close_cur > last_swing_low:
            bull_sweep_bars.append(i)

    # 4. Confluence Scoring (Total 10 Points)
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

    bull_score = 0
    bear_score = 0

    # 1. Structure
    bull_score += 1 if structure_bias == 1 else 0
    bear_score += 1 if structure_bias == -1 else 0

    # 2. Sweeps
    bull_score += 1 if any(current_idx - b <= 8 for b in bull_sweep_bars) else 0
    bear_score += 1 if any(current_idx - b <= 8 for b in bear_sweep_bars) else 0

    # 3. BOS / MSS
    bull_score += 1 if any(current_idx - b <= 8 for b in bull_break_bars) else 0
    bear_score += 1 if any(current_idx - b <= 8 for b in bear_break_bars) else 0

    # 4. Displacement
    bull_score += 1 if df['BullDisp'].iloc[-4:].any() else 0
    bear_score += 1 if df['BearDisp'].iloc[-4:].any() else 0

    # 5. Volume
    bull_score += 1 if df['HighVolume'].iloc[-4:].any() else 0
    bear_score += 1 if df['HighVolume'].iloc[-4:].any() else 0

    # 6. FVG
    bull_score += 1 if bull_fvg else 0
    bear_score += 1 if bear_fvg else 0

    # 7. VWAP
    bull_score += 1 if latest_close > latest_vwap else 0
    bear_score += 1 if latest_close < latest_vwap else 0

    # 8. HTF Bias
    bull_score += 1 if htf_bull else 0
    bear_score += 1 if htf_bear else 0

    # 9. Session (Crypto 24/7)
    bull_score += 1
    bear_score += 1

    # 10. Key S/R
    bull_score += 1 if (last_swing_low and abs(latest_close - last_swing_low) <= latest_atr * 1.5) else 0
    bear_score += 1 if (last_swing_high and abs(latest_close - last_swing_high) <= latest_atr * 1.5) else 0

    # 5. DIRECT TRIGGER (Agar Score >= 6 hai, toh alert send karo)
    long_trigger = (bull_score >= min_score) and (bull_score > bear_score)
    short_trigger = (bear_score >= min_score) and (bear_score > bull_score)

    # Auto Fib OTE Range
    ote_str = "N/A"
    if last_swing_high and last_swing_low:
        dist = abs(last_swing_high - last_swing_low)
        if last_high_bar and last_low_bar and last_high_bar > last_low_bar:
            f1, f2 = last_swing_high - dist * 0.618, last_swing_high - dist * 0.786
            ote_str = f"`{min(f1, f2):.2f} - {max(f1, f2):.2f}`"
        elif last_high_bar and last_low_bar:
            f1, f2 = last_swing_low + dist * 0.618, last_swing_low + dist * 0.786
            ote_str = f"`{min(f1, f2):.2f} - {max(f1, f2):.2f}`"

    clean_symbol = symbol.replace("-USD", "").replace("=F", "")

    # 6. Clean 4-Line Telegram Alert Format
    if long_trigger:
        msg = (
            f"🟢 *{clean_symbol} | BUY SETUP* (Score: {bull_score}/10)\n"
            f"💵 Price: `{latest_close:.2f}`\n"
            f"🎯 Setup: Confluence Reached\n"
            f"📦 OTE Zone: {ote_str}"
        )
        return {"signal": True, "type": "LONG", "message": msg}

    if short_trigger:
        msg = (
            f"🔴 *{clean_symbol} | SELL SETUP* (Score: {bear_score}/10)\n"
            f"💵 Price: `{latest_close:.2f}`\n"
            f"🎯 Setup: Confluence Reached\n"
            f"📦 OTE Zone: {ote_str}"
        )
        return {"signal": True, "type": "SHORT", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
