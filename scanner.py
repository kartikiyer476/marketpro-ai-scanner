import numpy as np
import pandas as pd
import pandas_ta as ta

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    """
    Pine Script: MarketPro AI - SMC Confluence PRO + Auto Fib
    LTF: 15m, HTF: 1h
    """
    if df_ltf.empty or len(df_ltf) < 60:
        return {"signal": False}

    df = df_ltf.copy()

    # 1. Inputs & Parameters
    pivot_len = 5
    atr_len = 14
    disp_atr_mult = 1.2
    disp_body_pct = 0.60
    vol_len = 20
    vol_mult = 1.4
    fvg_min_atr = 0.10
    sweep_max_bars = 30
    min_score = 7
    strict_sweep = True
    strict_mss = True
    strict_disp = True

    # 2. Core Indicators
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=atr_len)
    df['VolMA'] = df['Volume'].rolling(window=vol_len).mean()
    df['HighVolume'] = df['Volume'] > (df['VolMA'] * vol_mult)

    candle_range = df['High'] - df['Low']
    body = (df['Close'] - df['Open']).abs()
    body_pct = np.where(candle_range > 0, body / candle_range, 0.0)

    df['BullDisp'] = (df['Close'] > df['Open']) & (candle_range >= df['ATR'] * disp_atr_mult) & (body_pct >= disp_body_pct)
    df['BearDisp'] = (df['Close'] < df['Open']) & (candle_range >= df['ATR'] * disp_atr_mult) & (body_pct >= disp_body_pct)

    # VWAP Calculation
    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    if df['VWAP'].isna().all():
        hlc3 = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (hlc3 * df['Volume']).cumsum() / df['Volume'].cumsum()

    # 3. Swings (Pivot Highs / Lows)
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)

    last_swing_high = None
    prev_swing_high = None
    last_swing_low = None
    prev_swing_low = None
    last_high_bar = None
    last_low_bar = None
    structure_bias = 0

    bull_break_bars = []
    bear_break_bars = []
    bull_sweep_bars = []
    bear_sweep_bars = []

    for i in range(pivot_len, n - pivot_len):
        current_bar = i

        # Pivot High confirmation at current_bar
        is_ph = True
        for j in range(1, pivot_len + 1):
            if highs[i - pivot_len] <= highs[i - pivot_len - j] or highs[i - pivot_len] <= highs[i - pivot_len + j]:
                is_ph = False
                break
        if is_ph:
            ph = highs[i - pivot_len]
            prev_swing_high = last_swing_high
            last_swing_high = ph
            last_high_bar = i - pivot_len
            if prev_swing_high is not None:
                if ph > prev_swing_high:
                    structure_bias = 1
                elif ph < prev_swing_high:
                    structure_bias = -1

        # Pivot Low confirmation at current_bar
        is_pl = True
        for j in range(1, pivot_len + 1):
            if lows[i - pivot_len] >= lows[i - pivot_len - j] or lows[i - pivot_len] >= lows[i - pivot_len + j]:
                is_pl = False
                break
        if is_pl:
            pl = lows[i - pivot_len]
            prev_swing_low = last_swing_low
            last_swing_low = pl
            last_low_bar = i - pivot_len
            if prev_swing_low is not None:
                if pl > prev_swing_low:
                    structure_bias = 1
                elif pl < prev_swing_low:
                    structure_bias = -1

        # BOS / MSS detection
        close_cur = df['Close'].iloc[i]
        close_prev = df['Close'].iloc[i - 1]

        if last_swing_high is not None and close_cur > last_swing_high and close_prev <= last_swing_high:
            structure_bias = 1
            bull_break_bars.append(i)

        if last_swing_low is not None and close_cur < last_swing_low and close_prev >= last_swing_low:
            structure_bias = -1
            bear_break_bars.append(i)

        # Liquidity Sweeps
        if last_swing_high is not None and last_high_bar is not None and (i - last_high_bar <= sweep_max_bars):
            if df['High'].iloc[i] > last_swing_high and close_cur < last_swing_high:
                bear_sweep_bars.append(i)  # Buy-side swept (Bearish)

        if last_swing_low is not None and last_low_bar is not None and (i - last_low_bar <= sweep_max_bars):
            if df['Low'].iloc[i] < last_swing_low and close_cur > last_swing_low:
                bull_sweep_bars.append(i)  # Sell-side swept (Bullish)

    # 4. Fair Value Gaps (FVG)
    bull_fvg_series = (df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) >= df['ATR'] * fvg_min_atr)
    bear_fvg_series = (df['High'] < df['Low'].shift(2)) & ((df['Low'].shift(2) - df['High']) >= df['ATR'] * fvg_min_atr)

    # 5. Recent Event Memory (Bars since)
    current_idx = n - 1
    recent_bull_sweep = any(current_idx - b <= 5 for b in bull_sweep_bars)
    recent_bear_sweep = any(current_idx - b <= 5 for b in bear_sweep_bars)

    recent_bull_break = any(current_idx - b <= 5 for b in bull_break_bars)
    recent_bear_break = any(current_idx - b <= 5 for b in bear_break_bars)

    recent_bull_disp = df['BullDisp'].iloc[-3:].any()
    recent_bear_disp = df['BearDisp'].iloc[-3:].any()

    recent_high_vol = df['HighVolume'].iloc[-3:].any()
    recent_bull_fvg = bull_fvg_series.iloc[-8:].any()
    recent_bear_fvg = bear_fvg_series.iloc[-8:].any()

    # 6. VWAP Bias
    latest_close = df['Close'].iloc[-1]
    latest_vwap = df['VWAP'].iloc[-1]
    bull_vwap = latest_close > latest_vwap
    bear_vwap = latest_close < latest_vwap

    # 7. Higher Timeframe (1h EMA 50)
    htf_bull = True
    htf_bear = True
    if not df_htf.empty and len(df_htf) >= 50:
        df_htf['EMA50'] = ta.ema(df_htf['Close'], length=50)
        htf_close = df_htf['Close'].iloc[-1]
        htf_ema = df_htf['EMA50'].iloc[-1]
        htf_bull = htf_close > htf_ema
        htf_bear = htf_close < htf_ema

    # 8. Support / Resistance
    latest_atr = df['ATR'].iloc[-1]
    near_support = (last_swing_low is not None) and abs(latest_close - last_swing_low) <= latest_atr * 1.5
    near_resistance = (last_swing_high is not None) and abs(latest_close - last_swing_high) <= latest_atr * 1.5

    # 9. Session (Crypto runs 24/7)
    active_session = True

    # 10. Confluence Scoring (Max 10)
    bull_score = 0
    bear_score = 0

    bull_score += 1 if structure_bias == 1 else 0
    bear_score += 1 if structure_bias == -1 else 0

    bull_score += 1 if recent_bull_sweep else 0
    bear_score += 1 if recent_bear_sweep else 0

    bull_score += 1 if recent_bull_break else 0
    bear_score += 1 if recent_bear_break else 0

    bull_score += 1 if recent_bull_disp else 0
    bear_score += 1 if recent_bear_disp else 0

    bull_score += 1 if recent_high_vol else 0
    bear_score += 1 if recent_high_vol else 0

    bull_score += 1 if recent_bull_fvg else 0
    bear_score += 1 if recent_bear_fvg else 0

    bull_score += 1 if bull_vwap else 0
    bear_score += 1 if bear_vwap else 0

    bull_score += 1 if htf_bull else 0
    bear_score += 1 if htf_bear else 0

    bull_score += 1 if active_session else 0
    bear_score += 1 if active_session else 0

    bull_score += 1 if near_support else 0
    bear_score += 1 if near_resistance else 0

    # 11. Strict Confirmation Filters
    bull_req = (not strict_sweep or recent_bull_sweep) and \
               (not strict_mss or recent_bull_break) and \
               (not strict_disp or recent_bull_disp) and \
               htf_bull

    bear_req = (not strict_sweep or recent_bear_sweep) and \
               (not strict_mss or recent_bear_break) and \
               (not strict_disp or recent_bear_disp) and \
               htf_bear

    long_signal = (bull_score >= min_score) and bull_req
    short_signal = (bear_score >= min_score) and bear_req

    # 12. Auto Fibonacci / OTE Levels
    ote_info = "N/A"
    if last_swing_high and last_swing_low and last_high_bar and last_low_bar:
        fib_dist = abs(last_swing_high - last_swing_low)
        if last_high_bar > last_low_bar:
            ote_618 = last_swing_high - fib_dist * 0.618
            ote_786 = last_swing_high - fib_dist * 0.786
            ote_info = f"`{min(ote_618, ote_786):.2f} - {max(ote_618, ote_786):.2f}` (BULL OTE)"
        else:
            ote_618 = last_swing_low + fib_dist * 0.618
            ote_786 = last_swing_low + fib_dist * 0.786
            ote_info = f"`{min(ote_618, ote_786):.2f} - {max(ote_618, ote_786):.2f}` (BEAR OTE)"

    if long_signal:
        msg = (
            f"🟢 *MARKETPRO SMC - LONG CONFIRMED*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"• *Asset:* `{symbol}` (15m)\n"
            f"• *Price:* `{latest_close:.2f}`\n"
            f"• *Confluence Score:* `{bull_score}/10`\n"
            f"• *Liquidity:* SSL Swept ✅\n"
            f"• *Structure:* Bull MSS/BOS ✅\n"
            f"• *Displacement:* Active Bullish Body ✅\n"
            f"• *HTF 1H Bias:* Bullish (Above EMA 50) ✅\n"
            f"• *Auto Fib OTE:* {ote_info}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ _MarketPro AI Confluence Engine_"
        )
        return {"signal": True, "type": "LONG", "message": msg}

    if short_signal:
        msg = (
            f"🔴 *MARKETPRO SMC - SHORT CONFIRMED*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"• *Asset:* `{symbol}` (15m)\n"
            f"• *Price:* `{latest_close:.2f}`\n"
            f"• *Confluence Score:* `{bear_score}/10`\n"
            f"• *Liquidity:* BSL Swept ✅\n"
            f"• *Structure:* Bear MSS/BOS ✅\n"
            f"• *Displacement:* Active Bearish Body ✅\n"
            f"• *HTF 1H Bias:* Bearish (Below EMA 50) ✅\n"
            f"• *Auto Fib OTE:* {ote_info}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ _MarketPro AI Confluence Engine_"
        )
        return {"signal": True, "type": "SHORT", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
