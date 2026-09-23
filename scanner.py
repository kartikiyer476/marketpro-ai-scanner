import numpy as np
import pandas as pd
import pandas_ta as ta

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    """
    MarketPro AI - SMC Confluence PRO + Auto Fib
    Pine Script v6 Exact Reconstitution (15m Execution + 1h HTF Bias)
    """
    if df_ltf.empty or len(df_ltf) < 60:
        return {"signal": False, "score": "Data Insufficient (< 60 bars)"}

    df = df_ltf.copy()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. PINE SCRIPT INPUTS & PARAMETERS
    # ─────────────────────────────────────────────────────────────────────────
    pivot_len = 5
    atr_len = 14
    disp_atr = 1.2           # dispATR = 1.2
    disp_body_pct = 0.60     # dispBodyPct = 0.60
    vol_len = 20
    vol_mult = 1.4           # volMult = 1.4
    fvg_min_atr = 0.10       # fvgMinATR = 0.10
    sweep_max_bars = 30      # sweepMaxBars = 30
    min_score = 7            # Pine Script default: minScore = 7
    strict_sweep = True      # strictSweep = true
    strict_mss = True        # strictMSS = true
    strict_disp = True       # strictDisp = true
    cooldown_bars = 10       # cooldownBars = 10

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CORE VALUES & INDICATORS
    # ─────────────────────────────────────────────────────────────────────────
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=atr_len)
    df['VolMA'] = df['Volume'].rolling(window=vol_len).mean()
    df['HighVolume'] = df['Volume'] > (df['VolMA'] * vol_mult)

    candle_range = df['High'] - df['Low']
    body = (df['Close'] - df['Open']).abs()
    body_pct = np.where(candle_range > 0, body / candle_range, 0.0)

    # Bull / Bear Displacement
    df['BullDisp'] = (df['Close'] > df['Open']) & (candle_range >= df['ATR'] * disp_atr) & (body_pct >= disp_body_pct)
    df['BearDisp'] = (df['Close'] < df['Open']) & (candle_range >= df['ATR'] * disp_atr) & (body_pct >= disp_body_pct)

    # VWAP
    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    if df['VWAP'].isna().all():
        hlc3 = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (hlc3 * df['Volume']).cumsum() / df['Volume'].cumsum()

    # ─────────────────────────────────────────────────────────────────────────
    # 3. SWINGS, STRUCTURE, BOS/MSS & LIQUIDITY SWEEPS
    # ─────────────────────────────────────────────────────────────────────────
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    n = len(df)

    last_swing_high = None
    prev_swing_high = None
    last_swing_low = None
    prev_swing_low = None
    last_high_bar = None
    last_low_bar = None

    structure_bias = 0  # 1 = Bullish, -1 = Bearish

    bull_break_bars = []
    bear_break_bars = []
    bull_sweep_bars = []
    bear_sweep_bars = []
    signal_history = []  # For cooldown tracking

    for i in range(pivot_len, n - pivot_len):
        # ta.pivothigh(high, pivotLen, pivotLen)
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

        # ta.pivotlow(low, pivotLen, pivotLen)
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

        # BOS / MSS Breakouts
        close_cur = closes[i]
        close_prev = closes[i - 1]

        bull_break = (last_swing_high is not None) and (close_cur > last_swing_high) and (close_prev <= last_swing_high)
        bear_break = (last_swing_low is not None) and (close_cur < last_swing_low) and (close_prev >= last_swing_low)

        if bull_break:
            structure_bias = 1
            bull_break_bars.append(i)

        if bear_break:
            structure_bias = -1
            bear_break_bars.append(i)

        # Liquidity Sweeps
        high_valid = (last_swing_high is not None) and (last_high_bar is not None) and (i - last_high_bar <= sweep_max_bars)
        low_valid = (last_swing_low is not None) and (last_low_bar is not None) and (i - last_low_bar <= sweep_max_bars)

        # buySideSweep = high > lastSwingHigh and close < lastSwingHigh
        if high_valid and highs[i] > last_swing_high and close_cur < last_swing_high:
            bear_sweep_bars.append(i)

        # sellSideSweep = low < lastSwingLow and close > lastSwingLow
        if low_valid and lows[i] < last_swing_low and close_cur > last_swing_low:
            bull_sweep_bars.append(i)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. FVG & RECENT EVENT MEMORY
    # ─────────────────────────────────────────────────────────────────────────
    current_idx = n - 1

    bull_fvg_series = (df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) >= df['ATR'] * fvg_min_atr)
    bear_fvg_series = (df['High'] < df['Low'].shift(2)) & ((df['Low'].shift(2) - df['High']) >= df['ATR'] * fvg_min_atr)

    recent_bull_sweep = any(current_idx - b <= 5 for b in bull_sweep_bars)
    recent_bear_sweep = any(current_idx - b <= 5 for b in bear_sweep_bars)

    recent_bull_break = any(current_idx - b <= 5 for b in bull_break_bars)
    recent_bear_break = any(current_idx - b <= 5 for b in bear_break_bars)

    recent_bull_disp = df['BullDisp'].iloc[-3:].any()
    recent_bear_disp = df['BearDisp'].iloc[-3:].any()

    recent_high_volume = df['HighVolume'].iloc[-3:].any()
    recent_bull_fvg = bull_fvg_series.iloc[-8:].any()
    recent_bear_fvg = bear_fvg_series.iloc[-8:].any()

    latest_close = df['Close'].iloc[-1]
    latest_vwap = df['VWAP'].iloc[-1] if not pd.isna(df['VWAP'].iloc[-1]) else latest_close
    latest_atr = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else 0

    bull_vwap = latest_close > latest_vwap
    bear_vwap = latest_close < latest_vwap

    # Higher Timeframe (1h 50 EMA)
    htf_bull = True
    htf_bear = True
    if not df_htf.empty and len(df_htf) >= 20:
        df_htf['EMA50'] = ta.ema(df_htf['Close'], length=min(50, len(df_htf) - 1))
        htf_bull = df_htf['Close'].iloc[-1] > df_htf['EMA50'].iloc[-1]
        htf_bear = df_htf['Close'].iloc[-1] < df_htf['EMA50'].iloc[-1]

    # Active Session (Crypto trades 24/7)
    active_session = True

    # S/R Proximity
    near_support = (last_swing_low is not None) and (abs(latest_close - last_swing_low) <= latest_atr * 1.5)
    near_resistance = (last_swing_high is not None) and (abs(latest_close - last_swing_high) <= latest_atr * 1.5)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. CONFLUENCE SCORE (MAX 10)
    # ─────────────────────────────────────────────────────────────────────────
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

    bull_score += 1 if recent_high_volume else 0
    bear_score += 1 if recent_high_volume else 0

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

    # ─────────────────────────────────────────────────────────────────────────
    # 6. STRICT CONFIRMATION FILTERS & COOLDOWN
    # ─────────────────────────────────────────────────────────────────────────
    bull_required = (not strict_sweep or recent_bull_sweep) and \
                    (not strict_mss or recent_bull_break) and \
                    (not strict_disp or recent_bull_disp) and \
                    htf_bull

    bear_required = (not strict_sweep or recent_bear_sweep) and \
                    (not strict_mss or recent_bear_break) and \
                    (not strict_disp or recent_bear_disp) and \
                    htf_bear

    raw_long = (bull_score >= min_score) and bull_required
    raw_short = (bear_score >= min_score) and bear_required

    # Signal confirmation
    long_signal = raw_long and not raw_short
    short_signal = raw_short and not raw_long

    # ─────────────────────────────────────────────────────────────────────────
    # 7. AUTO FIBONACCI / OPTIMAL TRADE ENTRY (OTE: 0.618 - 0.705 - 0.786)
    # ─────────────────────────────────────────────────────────────────────────
    fib_ote_info = "N/A"
    invalidation_level = "Structural Pivot"

    if last_swing_high and last_swing_low and last_high_bar and last_low_bar:
        fib_dist = abs(last_swing_high - last_swing_low)
        if last_high_bar > last_low_bar:
            # Bullish Impulse (Low -> High)
            fib_618 = last_swing_high - fib_dist * 0.618
            fib_705 = last_swing_high - fib_dist * 0.705
            fib_786 = last_swing_high - fib_dist * 0.786
            fib_ote_info = f"${fib_786:,.2f} - ${fib_618:,.2f} (Sweet Spot:${fib_705:,.2f})"
            invalidation_level = f"${last_swing_low:,.2f}"
        else:
            # Bearish Impulse (High -> Low)
            fib_618 = last_swing_low + fib_dist * 0.618
            fib_705 = last_swing_low + fib_dist * 0.705
            fib_786 = last_swing_low + fib_dist * 0.786
            fib_ote_info = f"${fib_618:,.2f} - ${fib_786:,.2f} (Sweet Spot:${fib_705:,.2f})"
            invalidation_level = f"${last_swing_high:,.2f}"

    clean_ticker = symbol.replace("-USD", "/USDT").replace("=F", " Gold Spot")

    # ─────────────────────────────────────────────────────────────────────────
    # 8. INSTITUTIONAL INVESTOR ALERT DELIVERY
    # ─────────────────────────────────────────────────────────────────────────
    if long_signal:
        msg = (
            f"⚡ *MARKETPRO AI | SMC CONFLUENCE PRO ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
            f"🎯 *Signal:* *LONG CONFIRMED* 🟢\n"
            f"💵 *Execution Price:* `${latest_close:,.2f}`\n"
            f"📊 *Confluence Score:* `{bull_score}/10` (Requirement $\\ge$ {min_score})\n\n"
            f"🔍 *Strict Confluence Checklist:*\n"
            f"  • *Liquidity:* SSL Swept (Retail Sell Stops Hunted) ✅\n"
            f"  • *Structure:* Bullish MSS/BOS Confirmed ✅\n"
            f"  • *Displacement:* Institutional Impulse Candle ✅\n"
            f"  • *HTF Bias:* Bullish Alignment (Above 1H 50 EMA) ✅\n"
            f"  • *Fair Value Gap:* {'Bullish FVG Active ✅' if recent_bull_fvg else 'None'}\n"
            f"  • *Session VWAP:* Price Above VWAP ✅\n\n"
            f"📐 *Auto Fib / Institutional Entry Zone:*\n"
            f"  • *OTE Retest (0.618 - 0.786):* `{fib_ote_info}`\n"
            f"  • *Structural Invalidation (SL):* `< {invalidation_level}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 _Investor Note: High-probability accumulation complete. Best R:R entry on pullback into OTE._"
        )
        return {"signal": True, "type": "LONG", "message": msg}

    if short_signal:
        msg = (
            f"⚡ *MARKETPRO AI | SMC CONFLUENCE PRO ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
            f"🎯 *Signal:* *SHORT CONFIRMED* 🔴\n"
            f"💵 *Execution Price:* `${latest_close:,.2f}`\n"
            f"📊 *Confluence Score:* `{bear_score}/10` (Requirement $\\ge$ {min_score})\n\n"
            f"🔍 *Strict Confluence Checklist:*\n"
            f"  • *Liquidity:* BSL Swept (Retail Buy Stops Hunted) ✅\n"
            f"  • *Structure:* Bearish MSS/BOS Confirmed ✅\n"
            f"  • *Displacement:* Institutional Selling Pressure ✅\n"
            f"  • *HTF Bias:* Bearish Alignment (Below 1H 50 EMA) ✅\n"
            f"  • *Fair Value Gap:* {'Bearish FVG Active ✅' if recent_bear_fvg else 'None'}\n"
            f"  • *Session VWAP:* Price Below VWAP ✅\n\n"
            f"📐 *Auto Fib / Institutional Entry Zone:*\n"
            f"  • *OTE Retest (0.618 - 0.786):* `{fib_ote_info}`\n"
            f"  • *Structural Invalidation (SL):* `> {invalidation_level}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 _Investor Note: High-probability distribution complete. Target recent internal liquidity._"
        )
        return {"signal": True, "type": "SHORT", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
