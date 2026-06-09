# Architecture

TradeMentor Paper Trading Bot is designed as a small automation system with separate components.

## Flow

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
Components
Signal Engine

The signal engine listens to Binance candlestick data and evaluates closed candles using configurable filters such as SMA, RSI, ATR and cooldown rules.

Webhook Server

The webhook server is built with FastAPI. It receives JSON signals, validates them and logs accepted paper trades.

Risk Layer

The risk layer rejects invalid or unsafe signals before they are logged.

Trade Manager

The trade manager checks current market prices and closes open paper trades when stop-loss or take-profit is reached.
