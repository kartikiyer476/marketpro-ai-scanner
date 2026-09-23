import numpy as np
import pandas as pd
import pandas_ta as ta
from crypto_meter import get_crypto_meter_data

def calculate_smc_confluence(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, symbol: str) -> dict:
    if df_ltf.empty or len(df_ltf) < 45:
        return {"signal": False, "score": "Data Insufficient"}

    df = df_ltf.copy()

    # 1. Core SMC Parameters
    pivot_len = 5
    atr_len = 14
    vol_len = 20

    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=atr_len)
    df['VolMA'] = df['Volume'].rolling(window=vol_len).mean()
    df['HighVolume'] = df['Volume'] > (df['VolMA'] * 1.25)

    candle_range = df['High'] - df['Low']
    body = (df['Close'] - df['Open']).abs()
    body_pct = np.where(candle_range > 0, body / candle_range, 0.0)

    df['BullDisp'] = (df['Close'] > df['Open']) & (candle_range >= df['ATR'] * 1.1) & (body_pct >= 0.52)
    df['BearDisp'] = (df['Close'] < df['Open']) & (candle_range >= df['ATR'] * 1.1) & (body_pct >= 0.52)

    df['VWAP'] = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
    if df['VWAP'].isna().all():
        hlc3 = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (hlc3 * df['Volume']).cumsum() / df['Volume'].cumsum()

    # 2. Market Structure & Swings
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    n = len(df)

    last_swing_high = None
    last_swing_low = None
    last_high_bar = None
    last_low_bar = None
    structure_bias = 0

    bull_break_bars, bear_break_bars = [], []
    bull_sweep_bars, bear_sweep_bars = [], []

    for i in range(pivot_len, n - pivot_len):
        if all(highs[i - pivot_len] >= highs[i - pivot_len - j] and highs[i - pivot_len] >= highs[i - pivot_len + j] for j in range(1, pivot_len + 1)):
            last_swing_high = highs[i - pivot_len]
            last_high_bar = i - pivot_len

        if all(lows[i - pivot_len] <= lows[i - pivot_len - j] and lows[i - pivot_len] <= lows[i - pivot_len + j] for j in range(1, pivot_len + 1)):
            last_swing_low = lows[i - pivot_len]
            last_low_bar = i - pivot_len

        if last_swing_high and closes[i] > last_swing_high and closes[i - 1] <= last_swing_high:
            structure_bias = 1
            bull_break_bars.append(i)

        if last_swing_low and closes[i] < last_swing_low and closes[i - 1] >= last_swing_low:
            structure_bias = -1
            bear_break_bars.append(i)

        if last_swing_high and highs[i] > last_swing_high and closes[i] < last_swing_high:
            bear_sweep_bars.append(i)

        if last_swing_low and lows[i] < last_swing_low and closes[i] > last_swing_low:
            bull_sweep_bars.append(i)

    current_idx = n - 1
    bull_fvg = ((df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) >= df['ATR'] * 0.08)).iloc[-6:].any()
    bear_fvg = ((df['High'] < df['Low'].shift(2)) & ((df['Low'].shift(2) - df['High']) >= df['ATR'] * 0.08)).iloc[-6:].any()

    latest_close = df['Close'].iloc[-1]
    latest_vwap = df['VWAP'].iloc[-1] if not pd.isna(df['VWAP'].iloc[-1]) else latest_close
    latest_atr = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (latest_close * 0.01)

    htf_bull, htf_bear = True, True
    if not df_htf.empty and len(df_htf) >= 20:
        df_htf['EMA50'] = ta.ema(df_htf['Close'], length=min(50, len(df_htf) - 1))
        htf_bull = df_htf['Close'].iloc[-1] >= df_htf['EMA50'].iloc[-1]
        htf_bear = df_htf['Close'].iloc[-1] <= df_htf['EMA50'].iloc[-1]

    # 3. LIVE CRYPTOMETER INTEGRATION
    cm = get_crypto_meter_data(symbol)

    bull_reasons, bear_reasons = [], []

    if structure_bias == 1:
        bull_reasons.append("Trend Alignment: Buyers continuous higher levels control kar rahe hain.")
    elif structure_bias == -1:
        bear_reasons.append("Trend Alignment: Sellers lower lows bana kar market push kar rahe hain.")

    if any(current_idx - b <= 8 for b in bull_sweep_bars):
        bull_reasons.append("Liquidity Trap: Retailers ke stop-loss hunt ho chuke hain (Whale Accumulation).")
    if any(current_idx - b <= 8 for b in bear_sweep_bars):
        bear_reasons.append("Liquidity Trap: Buyers trap ho chuke hain (Whale Distribution).")

    if any(current_idx - b <= 8 for b in bull_break_bars):
        bull_reasons.append("Orderflow Shift: Market structure ne upward reversal confirm kiya hai.")
    if any(current_idx - b <= 8 for b in bear_break_bars):
        bear_reasons.append("Orderflow Shift: Market structure ne downward breakdown confirm kiya hai.")

    if df['BullDisp'].iloc[-4:].any():
        bull_reasons.append("Displacement: Strong buying expansion candle detect hui hai.")
    if df['BearDisp'].iloc[-4:].any():
        bear_reasons.append("Displacement: Heavy selling breakdown candle print hui hai.")

    if df['HighVolume'].iloc[-4:].any():
        bull_reasons.append("Volume Footprint: Volume average se kafi high record hua hai.")
        bear_reasons.append("Volume Footprint: Volume average se kafi high record hua hai.")

    if bull_fvg:
        bull_reasons.append("Imbalance Zone: Fair Value Gap create hua hai (Bullish Magnet).")
    if bear_fvg:
        bear_reasons.append("Imbalance Zone: Bearish Fair Value Gap create hua hai.")

    if latest_close > latest_vwap:
        bull_reasons.append("Institutional VWAP: Price session average ke upar sustained hai.")
    else:
        bear_reasons.append("Institutional VWAP: Price session average ke niche reject ho raha hai.")

    if htf_bull:
        bull_reasons.append("Macro Bias: Higher timeframe primary trend bullish aligned hai.")
    if htf_bear:
        bear_reasons.append("Macro Bias: Higher timeframe primary trend bearish aligned hai.")

    bull_reasons.append("Market Liquidity: Active session execution confirm hai.")
    bear_reasons.append("Market Liquidity: Active session execution confirm hai.")

    if last_swing_low and abs(latest_close - last_swing_low) <= latest_atr * 1.5:
        bull_reasons.append("Major Level: Strong institutional support base par bounce ban raha hai.")
    if last_swing_high and abs(latest_close - last_swing_high) <= latest_atr * 1.5:
        bear_reasons.append("Major Level: Major supply resistance zone par rejection dekha gaya hai.")

    # CryptoMeter Boost
    if cm.get("available"):
        if cm["buy_pct"] >= 54.0:
            bull_reasons.append(f"CryptoMeter Flow: Buyers dominant hain ({cm['buy_pct']}% Buy Volume).")
        if cm["sell_pct"] >= 54.0:
            bear_reasons.append(f"CryptoMeter Flow: Sellers dominant hain ({cm['sell_pct']}% Sell Volume).")

    bull_score = len(bull_reasons)
    bear_score = len(bear_reasons)

    fresh_catalyst = (
        any(current_idx - b <= 3 for b in bull_break_bars + bear_break_bars + bull_sweep_bars + bear_sweep_bars) or
        df['BullDisp'].iloc[-3:].any() or df['BearDisp'].iloc[-3:].any()
    )

    if not fresh_catalyst:
        return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10 (No Fresh Catalyst)"}

    # 4. Levels Calculation
    ote_str = "Market Price"
    sl_price = latest_close - (latest_atr * 1.5)
    tp1 = latest_close + (latest_atr * 2.2)
    tp2 = latest_close + (latest_atr * 3.8)

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

    # Format CryptoMeter Block
    if cm.get("available"):
        total_m = cm["total_usd"] / 1_000_000
        delta_m = cm["net_flow_usd"] / 1_000_000
        delta_sign = "+" if delta_m > 0 else ""
        cm_block = (
            f"📊 *CryptoMeter™ Order Flow & Whale Action:*\n"
            f"  • *15m Volume:* `${total_m:.2f}M`\n"
            f"  • *Buy Pressure:* `{cm['buy_pct']}%` 🟢 | *Sell:* `{cm['sell_pct']}%` 🔴\n"
            f"  • *Net Institutional Delta:* `{delta_sign}${delta_m:.2f}M`\n"
            f"  • *Flow Verdict:* _{cm['status']}_\n"
        )
    else:
        cm_block = "📊 *Order Flow:* _Commodity Session Liquidity Active_\n"

    # 5. Bullish Alerts
    if bull_score >= 5 and bull_score > bear_score:
        reasons_text = "\n".join([f"  ▸ {r}" for r in bull_reasons[:4]])

        if bull_score >= 8:
            msg = (
                f"🔥 *MARKETPRO | A+ STRONG BUY SIGNAL*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Signal:* *HIGH CONVICTION BUY* 🟢\n"
                f"📊 *Proprietary Score:* `{bull_score}/10` (Maximum Confluence)\n"
                f"💵 *CMP (Current Price):* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"🧠 *Setup Validation (Hinglish):*\n"
                f"{reasons_text}\n\n"
                f"🎯 *Execution Setup:*\n"
                f"• *Entry:* `${latest_close:,.2f}` (Ya OTE Retest: `{ote_str}`)\n"
                f"• *Stop Loss:* `${sl_price:,.2f}`\n"
                f"• *Target 1:* `${tp1:,.2f}`\n"
                f"• *Target 2:* `${tp2:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ _Pro Tip: Heavy buy delta confirmation milte hi smart money ke sath ride karein._"
            )
            return {"signal": True, "type": "LONG_TIER3", "message": msg}

        elif bull_score == 7:
            msg = (
                f"⚡ *MARKETPRO | BUY SETUP CONFIRMED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Action:* *BUY SETUP READY* 🟢\n"
                f"📊 *Score:* `{bull_score}/10`\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"🔍 *Analysis:*\n{reasons_text}\n\n"
                f"📐 *Key Trade Levels:*\n"
                f"• *OTE Retest Zone:* `{ote_str}`\n"
                f"• *Invalidation (SL):* `< ${sl_price:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 _Advice: Retest level par green candle validation ke sath enter karein._"
            )
            return {"signal": True, "type": "LONG_TIER2", "message": msg}

        elif bull_score >= 5:
            msg = (
                f"⚠️ *MARKETPRO | BUY RADAR ALERT*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👀 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"📊 *Score:* `{bull_score}/10` (Early Accumulation)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"⏳ _Market Makers position build kar rahe hain. Watchlist par rakhein._"
            )
            return {"signal": True, "type": "LONG_TIER1", "message": msg}

    # 6. Bearish Alerts
    if bear_score >= 5 and bear_score > bull_score:
        reasons_text = "\n".join([f"  ▸ {r}" for r in bear_reasons[:4]])

        if bear_score >= 8:
            msg = (
                f"🔥 *MARKETPRO | A+ STRONG SELL SIGNAL*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Signal:* *HIGH CONVICTION SELL* 🔴\n"
                f"📊 *Proprietary Score:* `{bear_score}/10` (Maximum Confluence)\n"
                f"💵 *CMP (Current Price):* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"🧠 *Setup Validation (Hinglish):*\n"
                f"{reasons_text}\n\n"
                f"🎯 *Execution Setup:*\n"
                f"• *Entry:* `${latest_close:,.2f}` (Ya OTE Retest: `{ote_str}`)\n"
                f"• *Stop Loss:* `${sl_price:,.2f}`\n"
                f"• *Target 1:* `${tp1:,.2f}`\n"
                f"• *Target 2:* `${tp2:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ _Pro Tip: Heavy selling outflow active hai. Pullback rejection par short execute karein._"
            )
            return {"signal": True, "type": "SHORT_TIER3", "message": msg}

        elif bear_score == 7:
            msg = (
                f"⚡ *MARKETPRO | SELL SETUP CONFIRMED*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"🎯 *Action:* *SELL SETUP READY* 🔴\n"
                f"📊 *Score:* `{bear_score}/10`\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"🔍 *Analysis:*\n{reasons_text}\n\n"
                f"📐 *Key Trade Levels:*\n"
                f"• *OTE Retest Zone:* `{ote_str}`\n"
                f"• *Invalidation (SL):* `> ${sl_price:,.2f}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 _Advice: Supply zone retest rejection par entry plan karein._"
            )
            return {"signal": True, "type": "SHORT_TIER2", "message": msg}

        elif bear_score >= 5:
            msg = (
                f"⚠️ *MARKETPRO | SELL RADAR ALERT*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👀 *Asset:* `{clean_ticker}` (15m TF)\n"
                f"📊 *Score:* `{bear_score}/10` (Early Distribution)\n"
                f"💵 *Price:* `${latest_close:,.2f}`\n\n"
                f"{cm_block}\n"
                f"⏳ _Upper supply levels par selling buildup ho raha hai. Confirmation ka wait karein._"
            )
            return {"signal": True, "type": "SHORT_TIER1", "message": msg}

    return {"signal": False, "score": f"BULL: {bull_score}/10 | BEAR: {bear_score}/10"}
