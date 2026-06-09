from datetime import datetime, timedelta, timezone
import requests

SYMBOL = "BTCUSDT"
INTERVAL = "5m"
DAYS = 60

SMA_FAST = 20
SMA_SLOW = 50
RSI_LENGTH = 14
ATR_LENGTH = 14

ATR_STOP_MULT = 1.0
RR_TARGET = 2.0
RISK_PERCENT = 0.25

MAX_DAILY_TRADES = 3
MAX_DAILY_STOP_LOSSES = 2
COOLDOWN_CANDLES = 6


def ms(dt):
    return int(dt.timestamp() * 1000)


def sma(values, length):
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def rsi(closes, length):
    if len(closes) < length + 1:
        return None

    gains = []
    losses = []
    recent = closes[-(length + 1):]

    for i in range(1, len(recent)):
        diff = recent[i] - recent[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles, length):
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


def fetch_klines():
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=DAYS)

    rows = []
    current = start

    print(f"{SYMBOL} {INTERVAL} son {DAYS} gün indiriliyor...")

    while current < end:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "startTime": ms(current),
            "endTime": ms(end),
            "limit": 1000
        }

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if not data:
            break

        rows.extend(data)

        last_close_time = data[-1][6]
        current = datetime.fromtimestamp((last_close_time + 1) / 1000, tz=timezone.utc)

        print(f"İndirilen mum: {len(rows)}")

        if len(data) < 1000:
            break

    candles = []

    for k in rows:
        candles.append({
            "time": datetime.fromtimestamp(k[6] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "date": datetime.fromtimestamp(k[6] / 1000).strftime("%Y-%m-%d"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    print(f"Toplam mum: {len(candles)}")
    return candles


def close_trade_if_hit(trade, candle):
    side = trade["side"]
    high = candle["high"]
    low = candle["low"]

    if side == "BUY":
        hit_sl = low <= trade["stop"]
        hit_tp = high >= trade["take_profit"]

        if hit_sl:
            reason = "STOP_LOSS"
            close_price = trade["stop"]
        elif hit_tp:
            reason = "TAKE_PROFIT"
            close_price = trade["take_profit"]
        else:
            return None

    else:
        hit_sl = high >= trade["stop"]
        hit_tp = low <= trade["take_profit"]

        if hit_sl:
            reason = "STOP_LOSS"
            close_price = trade["stop"]
        elif hit_tp:
            reason = "TAKE_PROFIT"
            close_price = trade["take_profit"]
        else:
            return None

    if reason == "TAKE_PROFIT":
        pnl = RISK_PERCENT * RR_TARGET
    else:
        pnl = -RISK_PERCENT

    trade["status"] = "CLOSED"
    trade["close_time"] = candle["time"]
    trade["close_price"] = round(close_price, 2)
    trade["close_reason"] = reason
    trade["account_pnl_percent"] = round(pnl, 4)

    return trade


def run_backtest(candles):
    trades = []
    open_trade = None
    cooldown = 0

    daily_trade_count = {}
    daily_sl_count = {}

    start_i = max(SMA_SLOW, RSI_LENGTH, ATR_LENGTH) + 2

    for i in range(start_i, len(candles)):
        history = candles[:i]
        candle = candles[i]
        date = candle["date"]

        if open_trade:
            closed = close_trade_if_hit(open_trade, candle)

            if closed:
                trades.append(closed)

                if closed["close_reason"] == "STOP_LOSS":
                    daily_sl_count[date] = daily_sl_count.get(date, 0) + 1

                open_trade = None

            if open_trade:
                continue

        if cooldown > 0:
            cooldown -= 1
            continue

        if daily_trade_count.get(date, 0) >= MAX_DAILY_TRADES:
            continue

        if daily_sl_count.get(date, 0) >= MAX_DAILY_STOP_LOSSES:
            continue

        closes = [c["close"] for c in history]

        prev_close = closes[-2]
        curr_close = closes[-1]

        prev_fast = sma(closes[:-1], SMA_FAST)
        curr_fast = sma(closes, SMA_FAST)
        curr_slow = sma(closes, SMA_SLOW)
        curr_rsi = rsi(closes, RSI_LENGTH)
        curr_atr = atr(history, ATR_LENGTH)

        if None in [prev_fast, curr_fast, curr_slow, curr_rsi, curr_atr]:
            continue

        trend_up = curr_close > curr_slow and curr_fast > curr_slow
        trend_down = curr_close < curr_slow and curr_fast < curr_slow

        crossed_up_fast = prev_close <= prev_fast and curr_close > curr_fast
        crossed_down_fast = prev_close >= prev_fast and curr_close < curr_fast

        long_rsi_ok = 50 <= curr_rsi <= 68
        short_rsi_ok = 32 <= curr_rsi <= 50

        if trend_up and crossed_up_fast and long_rsi_ok:
            entry = curr_close
            stop = entry - (curr_atr * ATR_STOP_MULT)
            take_profit = entry + ((entry - stop) * RR_TARGET)

            open_trade = {
                "time": history[-1]["time"],
                "status": "OPEN",
                "symbol": SYMBOL,
                "side": "BUY",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "take_profit": round(take_profit, 2),
                "rr": RR_TARGET,
                "strategy": "filtered_sma_rsi_atr_backtest"
            }

            daily_trade_count[date] = daily_trade_count.get(date, 0) + 1
            cooldown = COOLDOWN_CANDLES
            continue

        if trend_down and crossed_down_fast and short_rsi_ok:
            entry = curr_close
            stop = entry + (curr_atr * ATR_STOP_MULT)
            take_profit = entry - ((stop - entry) * RR_TARGET)

            open_trade = {
                "time": history[-1]["time"],
                "status": "OPEN",
                "symbol": SYMBOL,
                "side": "SELL",
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "take_profit": round(take_profit, 2),
                "rr": RR_TARGET,
                "strategy": "filtered_sma_rsi_atr_backtest"
            }

            daily_trade_count[date] = daily_trade_count.get(date, 0) + 1
            cooldown = COOLDOWN_CANDLES
            continue

    return trades


def report(trades):
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    wins = [t for t in closed if t.get("close_reason") == "TAKE_PROFIT"]
    losses = [t for t in closed if t.get("close_reason") == "STOP_LOSS"]

    total_pnl = sum(float(t.get("account_pnl_percent", 0)) for t in closed)
    win_rate = (len(wins) / len(closed) * 100) if closed else 0

    print("\n==== BACKTEST RAPOR ====")
    print(f"Sembol: {SYMBOL}")
    print(f"Interval: {INTERVAL}")
    print(f"Gün: {DAYS}")
    print(f"Toplam kapalı işlem: {len(closed)}")
    print(f"Kazanan: {len(wins)}")
    print(f"Kaybeden: {len(losses)}")
    print(f"Win rate: %{win_rate:.2f}")
    print(f"Tahmini hesap PnL: %{total_pnl:.2f}")
    print(f"İşlem başı risk: %{RISK_PERCENT}")
    print(f"RR hedef: 1:{RR_TARGET}")

    print("\nSon 15 işlem:")
    for t in closed[-15:]:
        print(
            f"{t['time']} | {t['side']} | entry={t['entry']} | "
            f"close={t['close_price']} | {t['close_reason']} | "
            f"account_pnl={t['account_pnl_percent']}%"
        )


if __name__ == "__main__":
    candles = fetch_klines()
    trades = run_backtest(candles)
    report(trades)
