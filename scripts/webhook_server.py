from fastapi import FastAPI, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import os
import json

load_dotenv()

app = FastAPI(title="TradeMentor Execution Bot")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
MAX_RISK_PERCENT = float(os.getenv("MAX_RISK_PERCENT", "0.5"))
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "3"))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "1"))
PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() == "true"
ALLOWED_SYMBOLS = [s.strip().upper() for s in os.getenv("ALLOWED_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")]

MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "1.0"))
MAX_DAILY_STOP_LOSSES = int(os.getenv("MAX_DAILY_STOP_LOSSES", "2"))

LOG_DIR = Path("data/trades")
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADES_LOG = LOG_DIR / "paper_trades.jsonl"


class Signal(BaseModel):
    secret: str
    symbol: str
    side: str
    entry: float | None = None
    stop: float | None = None
    take_profit: float | None = None
    risk_percent: float = 0.5
    strategy: str = "unknown"
    note: str | None = None


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def load_all_trades():
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


def load_today_trades():
    return [t for t in load_all_trades() if t.get("date") == today_str()]


def count_open_trades():
    return len([t for t in load_all_trades() if t.get("status") == "OPEN"])


def today_closed_pnl_percent():
    total = 0.0
    for trade in load_today_trades():
        if trade.get("status") == "CLOSED":
            total += float(trade.get("pnl_percent", 0))
    return round(total, 4)


def today_stop_loss_count():
    return len([
        t for t in load_today_trades()
        if t.get("status") == "CLOSED" and t.get("close_reason") == "STOP_LOSS"
    ])


def calculate_rr(signal: Signal):
    if signal.entry is None or signal.stop is None or signal.take_profit is None:
        return None

    if signal.side.upper() == "BUY":
        risk = signal.entry - signal.stop
        reward = signal.take_profit - signal.entry
    elif signal.side.upper() == "SELL":
        risk = signal.stop - signal.entry
        reward = signal.entry - signal.take_profit
    else:
        return None

    if risk <= 0:
        return None

    return round(reward / risk, 2)


def validate_signal(signal: Signal):
    errors = []
    warnings = []

    symbol = signal.symbol.upper()
    side = signal.side.upper()

    if signal.secret != WEBHOOK_SECRET:
        errors.append("Secret yanlış. Sinyal reddedildi.")

    if symbol not in ALLOWED_SYMBOLS:
        errors.append(f"Sembol izinli değil: {symbol}. İzinli semboller: {ALLOWED_SYMBOLS}")

    if side not in ["BUY", "SELL"]:
        errors.append("Side sadece BUY veya SELL olabilir.")

    if signal.entry is None:
        errors.append("Entry fiyatı yok.")

    if signal.stop is None:
        errors.append("Stop-loss yok. Stop yoksa işlem yok.")

    if signal.take_profit is None:
        errors.append("Take-profit yok.")

    if signal.risk_percent <= 0:
        errors.append("Risk yüzdesi 0'dan büyük olmalı.")

    if signal.risk_percent > MAX_RISK_PERCENT:
        errors.append(f"Risk çok yüksek: %{signal.risk_percent}. Maksimum izin: %{MAX_RISK_PERCENT}")

    if len(load_today_trades()) >= MAX_DAILY_TRADES:
        errors.append(f"Günlük işlem limiti doldu. Limit: {MAX_DAILY_TRADES}")

    if count_open_trades() >= MAX_OPEN_TRADES:
        errors.append(f"Maksimum açık işlem limiti doldu. Limit: {MAX_OPEN_TRADES}")

    daily_pnl = today_closed_pnl_percent()
    if daily_pnl <= -abs(MAX_DAILY_LOSS_PERCENT):
        errors.append(f"Günlük zarar limiti aşıldı. Günlük PnL: %{daily_pnl}. Limit: -%{MAX_DAILY_LOSS_PERCENT}")

    sl_count = today_stop_loss_count()
    if sl_count >= MAX_DAILY_STOP_LOSSES:
        errors.append(f"Günlük stop-loss limiti doldu. Stop sayısı: {sl_count}. Limit: {MAX_DAILY_STOP_LOSSES}")

    rr = calculate_rr(signal)

    if rr is None:
        errors.append("Risk/ödül hesaplanamadı. Entry, stop ve take_profit yön ile uyumlu mu kontrol et.")
    elif rr < 2:
        warnings.append(f"Risk/ödül düşük görünüyor: 1:{rr}. En az 1:2 tercih edilmeli.")

    return errors, warnings, rr


def save_trade(signal: Signal, rr):
    record = {
        "date": today_str(),
        "time": datetime.now().isoformat(timespec="seconds"),
        "mode": "PAPER" if PAPER_MODE else "LIVE",
        "status": "OPEN",
        "symbol": signal.symbol.upper(),
        "side": signal.side.upper(),
        "entry": signal.entry,
        "stop": signal.stop,
        "take_profit": signal.take_profit,
        "risk_percent": signal.risk_percent,
        "rr": rr,
        "strategy": signal.strategy,
        "note": signal.note,
    }

    with TRADES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


@app.get("/")
def home():
    return {
        "app": "TradeMentor Execution Bot",
        "status": "running",
        "paper_mode": PAPER_MODE,
        "allowed_symbols": ALLOWED_SYMBOLS,
        "max_risk_percent": MAX_RISK_PERCENT,
        "max_daily_trades": MAX_DAILY_TRADES,
        "max_open_trades": MAX_OPEN_TRADES,
        "max_daily_loss_percent": MAX_DAILY_LOSS_PERCENT,
        "max_daily_stop_losses": MAX_DAILY_STOP_LOSSES,
        "today_pnl_percent": today_closed_pnl_percent(),
        "today_stop_loss_count": today_stop_loss_count(),
    }


@app.post("/webhook")
async def webhook(signal: Signal, request: Request):
    errors, warnings, rr = validate_signal(signal)

    if errors:
        return {
            "accepted": False,
            "decision": "REJECTED",
            "errors": errors,
            "warnings": warnings,
            "rr": rr,
        }

    trade = save_trade(signal, rr)

    return {
        "accepted": True,
        "decision": "PAPER_TRADE_LOGGED" if PAPER_MODE else "READY_FOR_LIVE_EXECUTION",
        "warnings": warnings,
        "rr": rr,
        "trade": trade,
    }


@app.get("/trades")
def trades():
    return {"trades": load_all_trades()[-100:]}
