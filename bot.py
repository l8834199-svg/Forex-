import os
import ccxt, time, pandas as pd, numpy as np
from telegram import Bot

# قراءة متغيرات البيئة
API_TOKEN = os.environ.get("API_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

bot = Bot(token=API_TOKEN)

SYMBOLS = ["EUR/USDT", "GBP/USDT", "USD/JPY", "XAU/USDT"]
TIMEFRAME = "5m"
EMA_FAST = 50
EMA_SLOW = 200
RSI_PERIOD = 14
STOP_POINTS = 0.0010
TARGET_POINTS = 0.0030

exchange = ccxt.binance()

def ema(series, period):
    return series.ewm(span=period).mean()

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1*delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/period, adjust=False).mean()
    ma_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = ma_up / (ma_down + 1e-10)
    return 100 - (100 / (1+rs))

def fetch_ohlcv(symbol):
    df = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=200),
                      columns=["time","open","high","low","close","volume"])
    df["close"] = df["close"].astype(float)
    return df

def generate_signal(symbol):
    df = fetch_ohlcv(symbol)
    df["ema_fast"] = ema(df["close"], EMA_FAST)
    df["ema_slow"] = ema(df["close"], EMA_SLOW)
    df["rsi"] = rsi(df["close"], RSI_PERIOD)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["close"] > last["ema_fast"] and last["close"] > last["ema_slow"]:
        trend = "buy"
    elif last["close"] < last["ema_fast"] and last["close"] < last["ema_slow"]:
        trend = "sell"
    else:
        return None

    if trend=="buy" and last["rsi"] > 70:
        return None
    if trend=="sell" and last["rsi"] < 30:
        return None

    recent_high = df["high"].iloc[-4:-1].max()
    recent_low = df["low"].iloc[-4:-1].min()
    entry = last["close"]
    if trend=="buy" and entry <= recent_high:
        return None
    if trend=="sell" and entry >= recent_low:
        return None

    avg_volume = df["volume"].iloc[-21:-1].mean()
    if last["volume"] < avg_volume:
        return None

    if trend=="buy":
        stop = round(entry - STOP_POINTS,5)
        target = round(entry + TARGET_POINTS,5)
    else:
        stop = round(entry + STOP_POINTS,5)
        target = round(entry - TARGET_POINTS,5)

    return (symbol, trend, round(entry,5), stop, target)

def send_signal(sig):
    symbol, trend, entry, stop, target = sig
    msg = f"""
📊 توصية تداول جديدة
الزوج: {symbol}
الإشارة: {'شراء' if trend=='buy' else 'بيع'}
الدخول: {entry}
⛔ ستوب: {stop}
🎯 هدف: {target}
"""
    bot.send_message(chat_id=CHANNEL_ID, text=msg)

while True:
    try:
        for sym in SYMBOLS:
            sig = generate_signal(sym)
            if sig:
                send_signal(sig)
        time.sleep(300)
    except Exception as e:
        print("خطأ:", e)
        time.sleep(60)
