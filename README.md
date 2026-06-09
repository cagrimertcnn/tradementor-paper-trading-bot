# TradeMentor Paper Trading Bot

A Linux-based automated paper trading system built with **Python**, **FastAPI**, **Binance market data**, webhook-based signal processing, risk management, trade tracking, backtesting and strategy optimization.

> This project does **not** execute real trades. It is designed for paper testing, automation learning, risk-management experiments and DevOps-style system building.

---

## Why I Built This

The goal of this project was to build a real-world automation system that combines:

* live market data processing,
* API/webhook communication,
* risk validation,
* background process management,
* JSON-based logging,
* strategy backtesting,
* parameter optimization,
* Linux-based service workflow.

Instead of only following tutorials, I wanted to build a working system end-to-end and document how the components communicate with each other.

---

## System Architecture

```text
Binance WebSocket Market Data
        |
        v
Filtered Signal Engine
        |
        v
FastAPI Webhook Server
        |
        v
Risk Management Layer
        |
        v
Paper Trade Log
        |
        v
Trade Manager
        |
        v
TP / SL Close Tracking
```

---

## Main Components

### 1. Webhook Server

`webhook_server.py`

A FastAPI service that receives trade signals, validates them and logs accepted paper trades.

It checks:

* webhook secret,
* allowed symbols,
* trade direction,
* entry / stop / take-profit values,
* max risk per trade,
* max daily trades,
* max open trades,
* max daily loss,
* max daily stop-loss count,
* risk/reward ratio.

---

### 2. Filtered Signal Engine

`filtered_signal_engine.py`

A market-data engine that listens to Binance candlestick data and generates paper trade signals using configurable filters.

Current filters include:

* SMA fast / slow trend filter,
* RSI range filter,
* ATR-based stop-loss,
* configurable risk/reward target,
* cooldown after signals.

---

### 3. Trade Manager

`trade_manager.py`

Tracks open paper trades and closes them when price reaches:

* stop-loss,
* take-profit.

It updates the trade log with:

* close time,
* close price,
* close reason,
* PnL percentage.

---

### 4. Report Script

`report.py`

Generates a quick performance summary:

* total trades,
* closed trades,
* open trades,
* winning trades,
* losing trades,
* win rate,
* total paper PnL,
* latest trade results.

---

### 5. Backtesting

`backtest_filtered.py`

Runs the strategy on historical Binance candlestick data and estimates past performance.

---

### 6. Optimizer

`optimizer.py`

Tests multiple parameter combinations and ranks strategy configurations based on:

* estimated PnL,
* win rate,
* trade count,
* max losing streak,
* risk/reward setup.

---

## Tech Stack

* Fedora Linux
* Python
* FastAPI
* Uvicorn
* Binance REST API
* Binance WebSocket stream
* JSONL logging
* dotenv configuration
* CLI-based process workflow

---

## Example Runtime Processes

The system is designed to run as three separate processes:

```bash
uvicorn scripts.webhook_server:app --host 127.0.0.1 --port 8000 --reload
python scripts/filtered_signal_engine.py
python scripts/trade_manager.py
```

---

## Example Risk Settings

```env
PAPER_MODE=true
MAX_RISK_PERCENT=0.5
MAX_DAILY_TRADES=3
MAX_OPEN_TRADES=1
MAX_DAILY_LOSS_PERCENT=1.0
MAX_DAILY_STOP_LOSSES=2
SIGNAL_RISK_PERCENT=0.25
RR_TARGET=1.5
```

---

## Screenshots

Screenshots will be added under the `screenshots/` directory.

Planned screenshots:

* running FastAPI server status,
* filtered signal engine terminal,
* paper trade log,
* trade report output,
* optimizer output,
* active Linux processes.

---

## Important Disclaimer

This project is for educational and paper-trading purposes only.

It does not provide financial advice, does not guarantee profit and should not be used for live trading without extensive testing, monitoring and risk controls.

---

## What This Project Demonstrates

This project demonstrates hands-on experience with:

* Linux terminal workflow,
* Python scripting,
* API service design,
* webhook-based automation,
* live data streaming,
* risk management logic,
* background process management,
* logging and reporting,
* backtesting and optimization,
* building and documenting an end-to-end automation system.
