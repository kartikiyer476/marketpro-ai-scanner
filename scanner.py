import numpy as np
import pandas as pd
import pandas_ta as ta

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    """
    MarketPro AI - 3-Tier Proprietary Smart Money Engine
    Tiers:
      • Score 5-6: Setup Alert (Early Radar)
      • Score 7: Setup Confirmed (High Probability)
      • Score 8-10: Strong Institutional Confirmed (Full Entry / SL / TP1 / TP2)
    """
    if df_ltf.empty or len(df_ltf) < 45:
        return {"signal": False, "score": "Data Insufficient"}

    df = df_ltf.copy()

    # 1. Proprietary Model Constants
    pivot_len = 5
    atr_len = 14
    vol_len = 20

    # 2. Indicators & Range Metrics
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=atr_len)
    df['VolMA'] = df['Volume'].rolling(window=vol_len).mean()
    df['HighVolume'] = df['Volume'] > (df['VolMA'] * 1.25)

    candle_range = df['High'] - df['Low']
    body = (df['Close'] - df['Open']).abs()
    body_pct = np.where(candle_range > 0, body / candle_range, 0.0)

    # Proprietary Displacement Footprint
    df['BullDisp'] = (df['Close'] > df['Open']) & (candle_range >= df['ATR'] * 1.1) & (body_pct >= 0.52)
    df['BearDisp'] = (df['Close'] < df['Open']) & (candle_range >= df['ATR'] * 1.1) & (body_pct >= 0.52)

    # Algorithmic Fair Value
    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    if df['VWAP'].isna().all():
        hlc3 = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (hlc3 * df['Volume']).cumsum() / df['Volume'].cumsum()

    # 3. Market Structure & Liquidity Mapping
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
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

        close_cur = closes[i]
        close_prev = closes[i - 1]

        # Structural Shifts
        if last_swing_high and close_cur > last_swing_high and close_prev <= last_swing_high:
            structure_bias = 1
            bull_break_bars.append(i)

        if last_swing_low and close_cur < last_swing_low and close_prev >= last_swing_low:
            structure_bias = -1
            bear_break_bars.append(i)

        # Liquidity Traps
        if last_swing_high and highs[i] > last_swing_high and close_cur < last_swing_high:
            bear_sweep_bars.append(i)

        if last_swing_low and lows[i] < last_swing_low and close_cur > last_swing_low:
            bull_sweep_bars.append(i)

    # 4. Multi-Confluence Engine
    current_idx = n - 1
    bull_fvg = ((df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) >= df['ATR'] * 0.08)).iloc[-6:].any()
    bear_fvg = ((df['High'] < df['Low'].shift(2)) & ((df['Low'].shift(2) - df['High']) >= df['ATR'] * 0.08)).iloc[-6:].any()

    latest_close = df['Close'].iloc[-1]
    latest_vwap = df['VWAP'].iloc[-1] if not pd.isna(df['VWAP'].iloc[-1]) else latest_close
    latest_atr = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (latest_close * 0.01)

    # Macro Alignment (HTF)
    htf_bull, htf_bear = True, True
    if not df_htf.empty and len(df_htf) >= 20:
        df_htf['EMA50'] = ta.ema(df_htf['Close'], length=min(50, len(df_htf) - 1))
        htf_bull = df_htf['Close'].iloc[-1] >= df_htf['EMA50'].iloc[-1]
        htf_bear = df_htf['Close'].iloc[-1] <= df_htf['EMA50'].iloc[-1]

    # Secret Black-Box Explanations (Hinglish Narrative)
    bull_reasons = []
    bear_reasons = []

    if structure_bias == 1:
        bull_reasons.append("Trend Alignment: Buyers continuous higher levels control kar rahe hain.")
    elif structure_bias == -1:
        bear_reasons.append("Trend Alignment: Sellers lower lows bana kar market ko push kar rahe hain.")

    if any(current_idx - b <= 8 for b in bull_sweep_bars):
        bull_reasons.append("Liquidity Trap: Retailers ke sell stop-loss hunt ho chuke hain (Smart Money Buy Zone).")
    if any(current_idx - b <= 8 for b in bear_sweep_bars):
        bear_reasons.append("Liquidity Trap: Retailers ke buy breakout traps execute ho chuke hain (Smart Money Sell Zone).")

    if any(current_idx - b <= 8 for b in bull_break_bars):
        bull_reasons.append("Orderflow Shift: Market structure ne buying side reversal confirm kiya hai.")
    if any(current_idx - b <= 8 for b in bear_break_bars):
        bear_reasons.append("Orderflow Shift: Market structure ne selling side breakdown confirm kiya hai.")

    if df['BullDisp'].iloc[-4:].any():
        bull_reasons.append("Aggressive Volume: Big institutions ki aggressive buying candle detect hui hai.")
    if df['BearDisp'].iloc[-4:].any():
        bear_reasons.append("Aggressive Volume: Institutional heavy sell-off candle print hui hai.")

    if df['HighVolume'].iloc[-4:].any():
        bull_reasons.append("Volume Footprint: Average se kafi zyada trading activity observe hui hai.")
        bear_reasons.append("Volume Footprint: Average se kafi zyada trading activity observe hui hai.")

    if bull_fvg:
        bull_reasons.append("Price Imbalance: Price ek sharp green gap chhod kar upar nikla hai (Magnet Level).")
    if bear_fvg:
        bear_reasons.append("Price Imbalance: Downside move par sharp imbalance zone create hua hai.")

    if latest_close > latest_vwap:
        bull_reasons.append("Fair Value: Price intraday institutional average ke upar sustain kar raha hai.")
    else:
        bear_reasons.append("Fair Value: Price intraday institutional average ke niche reject ho raha hai.")

    if htf_bull:
        bull_reasons.append("Macro Trend: Higher timeframe par primary trend bullish chal raha hai.")
    if htf_bear:
        bear_reasons.append("Macro Trend: Higher timeframe par primary trend bearish chal raha hai.")

    bull_reasons.append("Market Liquidity: Active session order execution active hai.")
    bear_reasons.append("Market Liquidity: Active session order execution active hai.")

    if last_swing_low and abs(latest_close - last_swing_low) <= latest_atr * 1.5:
        bull_reasons.append("Major Level: Strong institutional support base par bounce ban raha hai.")
    if last_swing_high and abs(latest_close - last_swing_high) <= latest_atr * 1.5:
        bear_reasons.append("Major Level: Major supply resistance zone par rejection dekha gaya hai.")

    bull_score = len(bull_reasons)
    bear_score = len(bear_reasons)

    # 5. Anti-Spam: Fresh Action Trigger (Pichli 3 candles me koi naya catalyst hona chahiye)
    fresh_catalyst = (
        any(current_idx - b <= 3 for b in bull_break_bars + bear_break_bars + bull_sweep_bars + bear_sweep_bars) or
        df['BullDisp'].iloc[-3:].any() or df['BearDisp'].iloc[-3:].any()
    )

    if not fresh_catalyst:
        return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10 (No Fresh Catalyst)"}

    # 6. Auto Fib / Trade Planning Math (Hidden Algorithmic Logic)
    ote_str = "Market Price"
    sl_price = latest_close - (latest_atr * 1.5)
    tp1 = latest_close + (latest_atr * 2.5)
    tp2 = latest_close + (latest_atr * 4.5)

    if last_swing_high and last_swing_low:
        dist = abs(last_swing_high - last_swing_low)
        if last_high_bar and last_low_bar and last_high_bar > last_low_bar:
            f1, f2 = last_swing_high - dist * 0.618, last_swing_high - dist * 0.786
            ote_str = f"${min(f1, f2):,.2f} -${max(f1, f2):,.2f}"
            sl_price = min(last_swing_low, latest_close - latest_atr * 1.2)
            risk = abs(latest_close - sl_price)
            tp1 = latest_close + (risk * 1.8)
            tp2 = latest_close + (risk * 3.2)
        elif last_high_bar and last_low_bar:
            f1, f2 = last_swing_low + dist * 0.618, last_swing_low + dist * 0.786
            ote_str = f"${min(f1, f2):,.2f} -${max(f1, f2):,.2f}"
            sl_price = max(last_swing_high, latest_close + latest_atr * 1.2)
            risk = abs(sl_price - latest_close)
            tp1 = latest_close - (risk * 1.8)
            tp2 = latest_close - (risk * 3.2)

    clean_ticker = symbol.replace("-USD", "/USDT").replace("=F", " Gold Spot")

    # ─────────────────────────────────────────────────────────────────────────
    # 7. TIERED NOTIFICATION ENGINE (BULLISH)
    # ─────────────────────────────────────────────────────────────────────────
    if bull_score >= 5 and bull_score > bear_score:
        reasons_text = "\n".join([f"  ▸ {r}" for r in bull_reasons[:4]])

        # TIER 3: STRONG CONFIRMED (Score 8 - 10)
        if bull_score >= 8:
            msg = (
                f"🔥 *MARKETPRO | A+ STRONG BUY SIGNAL*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Signal:* *HIGH CONVICTION BUY* 🟢\n"
                f"📊 *Proprietary Score:* `{bull_score}/10` (Maximum Confluence)\n"
                f"💵 *CMP (Current Price):* `${latest_close:,.2f}`\n\n"
                f"🧠 *Ye Setup Kyu Bana? (Market Analysis):*\n"
                f"{reasons_text}\n"
                f"  ▸ Smart money accumulation complete hai aur market expansion ke liye ready ho raha hai.\n\n"
                f"🎯 *Trade Execution Plan:*\n"
                f"• *Entry Zone:* `${latest_close:,.2f}` (Ya Pullback: `{ote_str}`)\n"
                f"• *Stop Loss (SL):* `${sl_price:,.2f}` (Strict Exit)\n"
                f"• *Target 1 (TP1):* `${tp1:,.2f}` (Risk-Reward 1:1.8)\n"
                f"• *Target 2 (TP2):* `${tp2:,.2f}` (Risk-Reward 1:3.2)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ _Execution Tip: Full target ke liye TP1 par 50% profit book karke SL entry par trail karein._"
            )
            return {"signal": True, "type": "LONG_TIER3", "message": msg}

        # TIER 2: SETUP CONFIRMED (Score 7)
        elif bull_score == 7:
            msg = (
                f"⚡ *MARKETPRO | SETUP CONFIRMED (BUY)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Status:* *BUY SETUP CONFIRMED* 🟢\n"
                f"📊 *Confluence Score:* `{bull_score}/10` (Strong Alignment)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"🔍 *Logic & Reasoning:*\n"
                f"{reasons_text}\n\n"
                f"📐 *Key Trade Levels:*\n"
                f"• *Watchlist Retest Zone:* `{ote_str}`\n"
                f"• *Structural Invalidation (SL Zone):* `< ${sl_price:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 _Advice: Setup confirm ho gaya hai. Retest aane par ya confirmation candle par entry plan karein._"
            )
            return {"signal": True, "type": "LONG_TIER2", "message": msg}

        # TIER 1: SETUP ALERT / RADAR (Score 5 - 6)
        elif bull_score >= 5:
            msg = (
                f"⚠️ *MARKETPRO | SETUP RADAR (BUY)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👀 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"📊 *Score:* `{bull_score}/10` (Early Buildup Phase)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"🔍 *Market Context:*\n"
                f"Smart money trap aur early volume inflow shuru ho chuka hai. Setup abhi develop ho raha hai, chart ko watchlist par rakhein.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ _Action: Confirmation ka wait karein, hasty entry na lein._"
            )
            return {"signal": True, "type": "LONG_TIER1", "message": msg}

    # ─────────────────────────────────────────────────────────────────────────
    # 8. TIERED NOTIFICATION ENGINE (BEARISH)
    # ─────────────────────────────────────────────────────────────────────────
    if bear_score >= 5 and bear_score > bull_score:
        reasons_text = "\n".join([f"  ▸ {r}" for r in bear_reasons[:4]])

        # TIER 3: STRONG CONFIRMED (Score 8 - 10)
        if bear_score >= 8:
            msg = (
                f"🔥 *MARKETPRO | A+ STRONG SELL SIGNAL*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Signal:* *HIGH CONVICTION SELL* 🔴\n"
                f"📊 *Proprietary Score:* `{bear_score}/10` (Maximum Confluence)\n"
                f"💵 *CMP (Current Price):* `${latest_close:,.2f}`\n\n"
                f"🧠 *Ye Setup Kyu Bana? (Market Analysis):*\n"
                f"{reasons_text}\n"
                f"  ▸ Institutions ne buy-stops clear karke distribution complete kar liya hai, downward pressure expected.\n\n"
                f"🎯 *Trade Execution Plan:*\n"
                f"• *Entry Zone:* `${latest_close:,.2f}` (Ya Pullback: `{ote_str}`)\n"
                f"• *Stop Loss (SL):* `${sl_price:,.2f}` (Strict Exit)\n"
                f"• *Target 1 (TP1):* `${tp1:,.2f}` (Risk-Reward 1:1.8)\n"
                f"• *Target 2 (TP2):* `${tp2:,.2f}` (Risk-Reward 1:3.2)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ _Execution Tip: Downside liquidity target karke TP1 aane par SL trailing shuru karein._"
            )
            return {"signal": True, "type": "SHORT_TIER3", "message": msg}

        # TIER 2: SETUP CONFIRMED (Score 7)
        elif bear_score == 7:
            msg = (
                f"⚡ *MARKETPRO | SETUP CONFIRMED (SELL)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Status:* *SELL SETUP CONFIRMED* 🔴\n"
                f"📊 *Confluence Score:* `{bear_score}/10` (Strong Alignment)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"🔍 *Logic & Reasoning:*\n"
                f"{reasons_text}\n\n"
                f"📐 *Key Trade Levels:*\n"
                f"• *Watchlist Retest Zone:* `{ote_str}`\n"
                f"• *Structural Invalidation (SL Zone):* `> ${sl_price:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 _Advice: Supply zone validation ho chuka hai. Pullback rejection par trade initiate karein._"
            )
            return {"signal": True, "type": "SHORT_TIER2", "message": msg}

        # TIER 1: SETUP ALERT / RADAR (Score 5 - 6)
        elif bear_score >= 5:
            msg = (
                f"⚠️ *MARKETPRO | SETUP RADAR (SELL)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👀 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"📊 *Score:* `{bear_score}/10` (Early Buildup Phase)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"🔍 *Market Context:*\n"
                f"Upper resistance par smart money distribution activity notice hui hai. Breakout ya breakdown ke liye monitor karein.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ _Action: Watchlist me add karein, premature entry avoid karein._"
            )
            return {"signal": True, "type": "SHORT_TIER1", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
