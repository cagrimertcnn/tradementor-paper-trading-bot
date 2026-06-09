from pathlib import Path
import json

TRADES_LOG = Path("data/trades/paper_trades.jsonl")

if not TRADES_LOG.exists():
    print("Henüz trade log yok.")
    raise SystemExit

trades = []

with TRADES_LOG.open("r", encoding="utf-8") as f:
    for line in f:
        try:
            trades.append(json.loads(line))
        except Exception:
            pass

closed = [t for t in trades if t.get("status") == "CLOSED"]
open_trades = [t for t in trades if t.get("status") == "OPEN"]

wins = [t for t in closed if float(t.get("pnl_percent", 0)) > 0]
losses = [t for t in closed if float(t.get("pnl_percent", 0)) < 0]

total_pnl = sum(float(t.get("pnl_percent", 0)) for t in closed)
win_rate = (len(wins) / len(closed) * 100) if closed else 0

print("==== TradeMentor Paper Rapor ====")
print(f"Toplam işlem: {len(trades)}")
print(f"Kapalı işlem: {len(closed)}")
print(f"Açık işlem: {len(open_trades)}")
print(f"Kazanan işlem: {len(wins)}")
print(f"Kaybeden işlem: {len(losses)}")
print(f"Win rate: %{win_rate:.2f}")
print(f"Toplam PnL: %{total_pnl:.4f}")

print("\nSon işlemler:")
for t in trades[-10:]:
    print(
        f"{t.get('time')} | {t.get('symbol')} {t.get('side')} | "
        f"{t.get('status')} | entry={t.get('entry')} | "
        f"close={t.get('close_price', '-')} | "
        f"reason={t.get('close_reason', '-')} | "
        f"pnl={t.get('pnl_percent', '-')}"
    )
