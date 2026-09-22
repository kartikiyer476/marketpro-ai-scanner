
import math

# -----------------------------
# ATR
# -----------------------------
def atr(candles, length=14):
    if len(candles) < length + 1:
        return None

    trs = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]

        tr = max(
            high-low,
            abs(high-prev_close),
            abs(low-prev_close)
        )

        trs.append(tr)

    return sum(trs[-length:])/length


# -----------------------------
# VWAP
# -----------------------------
def vwap(candles):
    pv = 0
    vol = 0

    for c in candles:
        tp = (c["high"]+c["low"]+c["close"])/3
        pv += tp*c["volume"]
        vol += c["volume"]

    if vol == 0:
        return None

    return pv/vol


# -----------------------------
# Volume Spike
# -----------------------------
def volume_spike(candles, length=20, mult=1.5):
    if len(candles) < length:
        return False

    vols = [c["volume"] for c in candles[-length:]]

    avg = sum(vols)/len(vols)

    return candles[-1]["volume"] > avg*mult


# -----------------------------
# Swing Detection
# -----------------------------
def market_structure(candles, pivot=5):

    if len(candles) < pivot*3:
        return None

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    last_high = max(highs[-pivot*2:-pivot])
    prev_high = max(highs[-pivot*3:-pivot*2])

    last_low = min(lows[-pivot*2:-pivot])
    prev_low = min(lows[-pivot*3:-pivot*2])

    if last_high > prev_high:
        structure = "BULL"
    elif last_low < prev_low:
        structure = "BEAR"
    else:
        structure = "RANGE"

    return {
        "structure": structure,
        "last_high": last_high,
        "last_low": last_low
    }


# -----------------------------
# BOS
# -----------------------------
def bos(candles, structure):

    close = candles[-1]["close"]

    bull = close > structure["last_high"]
    bear = close < structure["last_low"]

    return bull, bear


# -----------------------------
# Liquidity Sweep
# -----------------------------
def liquidity_sweep(candles, structure):

    last = candles[-1]

    buy = (
        last["high"] > structure["last_high"] and
        last["close"] < structure["last_high"]
    )

    sell = (
        last["low"] < structure["last_low"] and
        last["close"] > structure["last_low"]
    )

    return buy, sell


# -----------------------------
# Fibonacci
# -----------------------------
def fibonacci(candles):

    highs = [c["high"] for c in candles[-100:]]
    lows = [c["low"] for c in candles[-100:]]

    swing_high = max(highs)
    swing_low = min(lows)

    diff = swing_high-swing_low

    fib50 = swing_high-diff*0.5
    fib618 = swing_high-diff*0.618

    return {
        "50": fib50,
        "618": fib618
    }


# -----------------------------
# MarketPro Score
# -----------------------------
def score(candles):

    structure = market_structure(candles)

    if not structure:
        return None

    bull_bos, bear_bos = bos(candles, structure)

    buy_sweep, sell_sweep = liquidity_sweep(candles, structure)

    atr_val = atr(candles)

    vwap_val = vwap(candles)

    close = candles[-1]["close"]

    score_bull = 0
    score_bear = 0

    if structure["structure"] == "BULL":
        score_bull += 2

    if structure["structure"] == "BEAR":
        score_bear += 2

    if bull_bos:
        score_bull += 2

    if bear_bos:
        score_bear += 2

    if sell_sweep:
        score_bull += 1

    if buy_sweep:
        score_bear += 1

    if volume_spike(candles):
        score_bull += 1
        score_bear += 1

    if vwap_val and close > vwap_val:
        score_bull += 1

    if vwap_val and close < vwap_val:
        score_bear += 1

    fib = fibonacci(candles)

    if abs(close-fib["618"]) < atr_val:
        score_bull += 1
        score_bear += 1

    signal = "WAIT"

    if score_bull >= 7:
        signal = "LONG"

    if score_bear >= 7:
        signal = "SHORT"

    return {
        "signal": signal,
        "bull": score_bull,
        "bear": score_bear,
        "structure": structure["structure"],
        "fib": fib
    }
