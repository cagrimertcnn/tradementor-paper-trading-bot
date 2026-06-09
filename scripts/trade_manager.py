from pathlib import Path
from datetime import datetime
import json
import time
import requests

TRADES_LOG = Path("data/trades/paper_trades.jsonl")
CHECK_INTERVAL = 5


def now():
    return datetime.now().isoformat(timespec="seconds")


def load_trades():
    if not TRADES_LOG.exists():
        return []

    trades = []

    with TRADES_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except Exception:
                pass

    return trades


def save_trades(trades):
    TRADES_LOG.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = TRADES_LOG.with_suffix(".tmp")

    with tmp_file.open("w", encoding="utf-8") as f:
        for trade in trades:
            f.write(json.dumps(trade, ensure_ascii=False) + "\n")

    tmp_file.replace(TRADES_LOG)


def get_price(symbol):
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": symbol}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()

    return float(r.json()["price"])


def calculate_pnl_percent(trade, close_price):
    entry = float(trade["entry"])
    side = trade["side"].upper()

    if side == "BUY":
        return round(((close_price - entry) / entry) * 100, 4)

    if side == "SELL":
        return round(((entry - close_price) / entry) * 100, 4)

    return 0


def should_close_trade(trade, current_price):
    side = trade["side"].upper()
    stop = float(trade["stop"])
    take_profit = float(trade["take_profit"])

    if side == "BUY":
        if current_price <= stop:
            return True, "STOP_LOSS"
        if current_price >= take_profit:
            return True, "TAKE_PROFIT"

    if side == "SELL":
        if current_price >= stop:
            return True, "STOP_LOSS"
        if current_price <= take_profit:
            return True, "TAKE_PROFIT"

    return False, None


def manage_trades():
    trades = load_trades()
    open_trades = [t for t in trades if t.get("status") == "OPEN"]

    if not open_trades:
        print(f"[{now()}] Açık işlem yok.")
        return

    changed = False

    symbols = sorted(set(t["symbol"] for t in open_trades))

    prices = {}

    for symbol in symbols:
        try:
            prices[symbol] = get_price(symbol)
        except Exception as e:
            print(f"[{now()}] Fiyat alınamadı: {symbol} | {e}")

    for trade in trades:
        if trade.get("status") != "OPEN":
            continue

        symbol = trade["symbol"]
        current_price = prices.get(symbol)

        if current_price is None:
            continue

        close_now, reason = should_close_trade(trade, current_price)

        print(
            f"[{now()}] {symbol} {trade['side']} | "
            f"Entry: {trade['entry']} | Price: {current_price} | "
            f"SL: {trade['stop']} | TP: {trade['take_profit']}"
        )

        if close_now:
            pnl_percent = calculate_pnl_percent(trade, current_price)

            trade["status"] = "CLOSED"
            trade["close_time"] = now()
            trade["close_price"] = current_price
            trade["close_reason"] = reason
            trade["pnl_percent"] = pnl_percent

            changed = True

            print("\n==============================")
            print(f"İŞLEM KAPANDI: {reason}")
            print(f"Symbol: {symbol}")
            print(f"Side: {trade['side']}")
            print(f"Entry: {trade['entry']}")
            print(f"Close: {current_price}")
            print(f"PnL %: {pnl_percent}")
            print("==============================\n")

    if changed:
        save_trades(trades)


def run():
    print("Trade Manager başladı.")
    print(f"Kontrol aralığı: {CHECK_INTERVAL} saniye")
    print("Çıkmak için CTRL + C")

    while True:
        try:
            manage_trades()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("Trade Manager durduruldu.")
            break
        except Exception as e:
            print(f"[{now()}] Genel hata: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
