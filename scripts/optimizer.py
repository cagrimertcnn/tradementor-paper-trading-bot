from datetime import datetime, timedelta, timezone
import requests
import itertools

SYMBOL = "BTCUSDT"
INTERVAL = "5m"
DAYS = 60

RISK_PERCENT = 0.25
MAX_DAILY_TRADES = 3
MAX_DAILY_STOP_LOSSES = 2
COOLDOWN_CANDLES = 6

# İşlem maliyeti tahmini. Komisyon/slippage için her işlemden küçük ceza kesiyoruz.
COST_PER_TRADE_PNL = 0.03

SMA_FAST_LIST = [10, 20, 30]
SMA_SLOW_LIST = [50, 100, 150]
ATR_MULT_LIST = [1.0, 1.5, 2.0]
RR_LIST = [1.5, 2.0, 2.5, 3.0]

LONG_RSI_RANGES = [
    (50, 62),
    (50, 65),
    (52, 68),
    (55, 70),
]

SHORT_RSI_RANGES = [
    (38, 50),
    (35, 50),
    (32, 48),
    (30, 45),
]


def ms(dt):
    return int(dt.timestamp() * 1000)


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

        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

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


def close_trade_if_hit(trade, candle, rr):
    high = candle["high"]
    low = candle["low"]

    if trade["side"] == "BUY":
        hit_sl = low <= trade["stop"]
        hit_tp = high >= trade["take_profit"]

        if hit_sl:
            reason = "STOP_LOSS"
        elif hit_tp:
            reason = "TAKE_PROFIT"
        else:
            return None

    else:
        hit_sl = high >= trade["stop"]
        hit_tp = low <= trade["take_profit"]

        if hit_sl:
            reason = "STOP_LOSS"
        elif hit_tp:
            reason = "TAKE_PROFIT"
        else:
            return None

    if reason == "TAKE_PROFIT":
        pnl = (RISK_PERCENT * rr) - COST_PER_TRADE_PNL
    else:
        pnl = -RISK_PERCENT - COST_PER_TRADE_PNL

    trade["status"] = "CLOSED"
    trade["close_reason"] = reason
    trade["account_pnl_percent"] = round(pnl, 4)
    return trade


def run_backtest(candles, params):
    sma_fast = params["sma_fast"]
    sma_slow = params["sma_slow"]
    atr_mult = params["atr_mult"]
    rr = params["rr"]
    long_rsi_min, long_rsi_max = params["long_rsi"]
    short_rsi_min, short_rsi_max = params["short_rsi"]

    trades = []
    open_trade = None
    cooldown = 0

    daily_trade_count = {}
    daily_sl_count = {}

    start_i = max(sma_slow, 14, 14) + 2

    for i in range(start_i, len(candles)):
        history = candles[:i]
        candle = candles[i]
        date = candle["date"]

        if open_trade:
            closed = close_trade_if_hit(open_trade, candle, rr)

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

        prev_fast = sma(closes[:-1], sma_fast)
        curr_fast = sma(closes, sma_fast)
        curr_slow = sma(closes, sma_slow)
        curr_rsi = rsi(closes, 14)
        curr_atr = atr(history, 14)

        if None in [prev_fast, curr_fast, curr_slow, curr_rsi, curr_atr]:
            continue

        trend_up = curr_close > curr_slow and curr_fast > curr_slow
        trend_down = curr_close < curr_slow and curr_fast < curr_slow

        crossed_up_fast = prev_close <= prev_fast and curr_close > curr_fast
        crossed_down_fast = prev_close >= prev_fast and curr_close < curr_fast

        long_rsi_ok = long_rsi_min <= curr_rsi <= long_rsi_max
        short_rsi_ok = short_rsi_min <= curr_rsi <= short_rsi_max

        if trend_up and crossed_up_fast and long_rsi_ok:
            entry = curr_close
            stop = entry - (curr_atr * atr_mult)
            take_profit = entry + ((entry - stop) * rr)

            open_trade = {
                "side": "BUY",
                "entry": entry,
                "stop": stop,
                "take_profit": take_profit,
                "status": "OPEN",
            }

            daily_trade_count[date] = daily_trade_count.get(date, 0) + 1
            cooldown = COOLDOWN_CANDLES
            continue

        if trend_down and crossed_down_fast and short_rsi_ok:
            entry = curr_close
            stop = entry + (curr_atr * atr_mult)
            take_profit = entry - ((stop - entry) * rr)

            open_trade = {
                "side": "SELL",
                "entry": entry,
                "stop": stop,
                "take_profit": take_profit,
                "status": "OPEN",
            }

            daily_trade_count[date] = daily_trade_count.get(date, 0) + 1
            cooldown = COOLDOWN_CANDLES
            continue

    return trades


def max_losing_streak(trades):
    max_streak = 0
    streak = 0

    for t in trades:
        if t["close_reason"] == "STOP_LOSS":
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return max_streak


def summarize(trades, params):
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    wins = [t for t in closed if t["close_reason"] == "TAKE_PROFIT"]
    losses = [t for t in closed if t["close_reason"] == "STOP_LOSS"]

    if len(closed) == 0:
        return None

    total_pnl = sum(float(t.get("account_pnl_percent", 0)) for t in closed)
    win_rate = len(wins) / len(closed) * 100
    mls = max_losing_streak(closed)

    return {
        **params,
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "max_losing_streak": mls,
    }


def optimize(candles):
    results = []

    combos = list(itertools.product(
        SMA_FAST_LIST,
        SMA_SLOW_LIST,
        ATR_MULT_LIST,
        RR_LIST,
        LONG_RSI_RANGES,
        SHORT_RSI_RANGES
    ))

    print(f"Toplam kombinasyon: {len(combos)}")

    for idx, combo in enumerate(combos, start=1):
        sma_fast, sma_slow, atr_mult, rr, long_rsi, short_rsi = combo

        if sma_fast >= sma_slow:
            continue

        params = {
            "sma_fast": sma_fast,
            "sma_slow": sma_slow,
            "atr_mult": atr_mult,
            "rr": rr,
            "long_rsi": long_rsi,
            "short_rsi": short_rsi,
        }

        trades = run_backtest(candles, params)
        summary = summarize(trades, params)

        if summary and summary["trades"] >= 20:
            results.append(summary)

        if idx % 50 == 0:
            print(f"Test edildi: {idx}/{len(combos)}")

    results.sort(key=lambda x: x["total_pnl"], reverse=True)
    return results


def print_results(results):
    print("\n==== EN İYİ 20 SONUÇ ====")

    if not results:
        print("Yeterli işlem üreten sonuç yok.")
        return

    for i, r in enumerate(results[:20], start=1):
        print(
            f"{i}. PnL=%{r['total_pnl']} | "
            f"Trade={r['trades']} | "
            f"Win=%{r['win_rate']} | "
            f"W/L={r['wins']}/{r['losses']} | "
            f"MaxLossStreak={r['max_losing_streak']} | "
            f"SMA={r['sma_fast']}/{r['sma_slow']} | "
            f"ATR={r['atr_mult']} | "
            f"RR={r['rr']} | "
            f"LRSI={r['long_rsi']} | "
            f"SRSI={r['short_rsi']}"
        )


if __name__ == "__main__":
    candles = fetch_klines()
    results = optimize(candles)
    print_results(results)
