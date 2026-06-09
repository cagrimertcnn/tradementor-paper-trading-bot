from dotenv import load_dotenv
from datetime import datetime
import os
import json
import time
import requests
import websocket

load_dotenv()

SYMBOL = os.getenv("SIGNAL_SYMBOL", "BTCUSDT").upper()
INTERVAL = os.getenv("SIGNAL_INTERVAL", "5m")
WEBHOOK_URL = os.getenv("LOCAL_WEBHOOK_URL", "http://127.0.0.1:8000/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

RISK_PERCENT = float(os.getenv("SIGNAL_RISK_PERCENT", "0.25"))

SMA_FAST = int(os.getenv("SMA_FAST", "20"))
SMA_SLOW = int(os.getenv("SMA_SLOW", "50"))
RSI_LENGTH = int(os.getenv("RSI_LENGTH", "14"))
ATR_LENGTH = int(os.getenv("ATR_LENGTH", "14"))

LONG_RSI_MIN = float(os.getenv("LONG_RSI_MIN", "50"))
LONG_RSI_MAX = float(os.getenv("LONG_RSI_MAX", "68"))
SHORT_RSI_MIN = float(os.getenv("SHORT_RSI_MIN", "32"))
SHORT_RSI_MAX = float(os.getenv("SHORT_RSI_MAX", "50"))

ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "1.0"))
RR_TARGET = float(os.getenv("RR_TARGET", "2.0"))

COOLDOWN_CANDLES = int(os.getenv("COOLDOWN_CANDLES", "6"))

candles = []
cooldown_left = 0


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sma(values, length):
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def rsi(closes, length=14):
    if len(closes) < length + 1:
        return None

    gains = []
    losses = []

    recent = closes[-(length + 1):]

    for i in range(1, len(recent)):
        change = recent[i] - recent[i - 1]
        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles, length=14):
    if len(candles) < length + 1:
        return None

    trs = []
    recent = candles[-(length + 1):]

    for i in range(1, len(recent)):
        high = recent[i]["high"]
        low = recent[i]["low"]
        prev_close = recent[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )

        trs.append(tr)

    return sum(trs) / length


def load_initial_klines():
    global candles

    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": 120
    }

    print(f"[{now()}] İlk mumlar çekiliyor: {SYMBOL} {INTERVAL}")

    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()

    data = r.json()

    # Son mum kapanmamış olabilir, onu atıyoruz.
    closed_klines = data[:-1]

    candles = []

    for k in closed_klines:
        candles.append({
            "time": datetime.fromtimestamp(k[6] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    closes = [c["close"] for c in candles]

    print(f"[{now()}] Başlangıç mum sayısı: {len(candles)}")
    print(f"[{now()}] Son kapanış: {closes[-1]}")
    print(f"[{now()}] SMA{SMA_FAST}: {round(sma(closes, SMA_FAST), 2)}")
    print(f"[{now()}] SMA{SMA_SLOW}: {round(sma(closes, SMA_SLOW), 2)}")
    print(f"[{now()}] RSI{RSI_LENGTH}: {round(rsi(closes, RSI_LENGTH), 2)}")
    print(f"[{now()}] ATR{ATR_LENGTH}: {round(atr(candles, ATR_LENGTH), 2)}")
    print(f"[{now()}] Long RSI aralığı: {LONG_RSI_MIN}-{LONG_RSI_MAX}")
    print(f"[{now()}] Short RSI aralığı: {SHORT_RSI_MIN}-{SHORT_RSI_MAX}")
    print(f"[{now()}] RR hedef: 1:{RR_TARGET}")


def masked_payload(payload):
    safe = dict(payload)
    safe["secret"] = "***hidden***"
    return safe


def send_signal(side, entry, stop, take_profit, candle_time, details):
    payload = {
        "secret": WEBHOOK_SECRET,
        "symbol": SYMBOL,
        "side": side,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "take_profit": round(take_profit, 2),
        "risk_percent": RISK_PERCENT,
        "strategy": "filtered_sma_rsi_atr",
        "note": f"{details} | candle_time={candle_time}"
    }

    print(f"\n[{now()}] SİNYAL ÜRETİLDİ:")
    print(json.dumps(masked_payload(payload), indent=2, ensure_ascii=False))

    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        print(f"[{now()}] Webhook cevap kodu: {r.status_code}")
        print(r.text)
    except Exception as e:
        print(f"[{now()}] Webhook gönderim hatası: {e}")


def evaluate():
    global cooldown_left

    if len(candles) < max(SMA_SLOW, RSI_LENGTH, ATR_LENGTH) + 2:
        print(f"[{now()}] Veri az. Mum sayısı: {len(candles)}")
        return

    if cooldown_left > 0:
        cooldown_left -= 1
        print(f"[{now()}] Cooldown aktif. Kalan mum: {cooldown_left}")
        return

    closes = [c["close"] for c in candles]

    prev_close = closes[-2]
    curr_close = closes[-1]

    prev_fast = sma(closes[:-1], SMA_FAST)
    curr_fast = sma(closes, SMA_FAST)

    curr_slow = sma(closes, SMA_SLOW)
    curr_rsi = rsi(closes, RSI_LENGTH)
    curr_atr = atr(candles, ATR_LENGTH)

    last_candle = candles[-1]
    candle_time = last_candle["time"]

    if None in [prev_fast, curr_fast, curr_slow, curr_rsi, curr_atr]:
        print(f"[{now()}] İndikatörler hazır değil.")
        return

    print(
        f"[{now()}] Close: {curr_close:.2f} | "
        f"SMA{SMA_FAST}: {curr_fast:.2f} | "
        f"SMA{SMA_SLOW}: {curr_slow:.2f} | "
        f"RSI: {curr_rsi:.2f} | "
        f"ATR: {curr_atr:.2f}"
    )

    trend_up = curr_close > curr_slow and curr_fast > curr_slow
    trend_down = curr_close < curr_slow and curr_fast < curr_slow

    crossed_up_fast = prev_close <= prev_fast and curr_close > curr_fast
    crossed_down_fast = prev_close >= prev_fast and curr_close < curr_fast

    long_rsi_ok = LONG_RSI_MIN <= curr_rsi <= LONG_RSI_MAX
    short_rsi_ok = SHORT_RSI_MIN <= curr_rsi <= SHORT_RSI_MAX

    # Çok küçük ATR varsa işlem açma
    if curr_atr <= 0:
        print(f"[{now()}] ATR geçersiz, sinyal yok.")
        return

    # LONG
    if trend_up and crossed_up_fast and long_rsi_ok:
        entry = curr_close
        stop = entry - (curr_atr * ATR_STOP_MULT)
        take_profit = entry + ((entry - stop) * RR_TARGET)

        send_signal(
            "BUY",
            entry,
            stop,
            take_profit,
            candle_time,
            f"Trend yukarı + SMA{SMA_FAST} reclaim + RSI uygun"
        )

        cooldown_left = COOLDOWN_CANDLES
        return

    # SHORT
    if trend_down and crossed_down_fast and short_rsi_ok:
        entry = curr_close
        stop = entry + (curr_atr * ATR_STOP_MULT)
        take_profit = entry - ((stop - entry) * RR_TARGET)

        send_signal(
            "SELL",
            entry,
            stop,
            take_profit,
            candle_time,
            f"Trend aşağı + SMA{SMA_FAST} reject + RSI uygun"
        )

        cooldown_left = COOLDOWN_CANDLES
        return

    print(f"[{now()}] Sinyal yok.")


def on_message(ws, message):
    global candles

    data = json.loads(message)

    if data.get("e") != "kline":
        return

    k = data["k"]

    if not k["x"]:
        return

    candle = {
        "time": datetime.fromtimestamp(k["T"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
    }

    candles.append(candle)
    candles = candles[-300:]

    evaluate()


def on_error(ws, error):
    print(f"[{now()}] WebSocket hata: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"[{now()}] WebSocket kapandı: {close_status_code} {close_msg}")


def on_open(ws):
    print(f"[{now()}] WebSocket bağlantısı açıldı.")
    print(f"[{now()}] İzlenen: {SYMBOL} {INTERVAL}")


def run():
    if not WEBHOOK_SECRET:
        print("HATA: .env içinde WEBHOOK_SECRET yok.")
        return

    load_initial_klines()

    stream = f"{SYMBOL.lower()}@kline_{INTERVAL}"
    url = f"wss://stream.binance.com:9443/ws/{stream}"

    print(f"[{now()}] Stream URL: {url}")

    while True:
        try:
            ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            ws.run_forever(ping_interval=20, ping_timeout=10)

        except KeyboardInterrupt:
            print(f"[{now()}] Kullanıcı durdurdu.")
            break
        except Exception as e:
            print(f"[{now()}] Genel hata: {e}")

        print(f"[{now()}] 5 saniye sonra yeniden bağlanılıyor...")
        time.sleep(5)


if __name__ == "__main__":
    run()
