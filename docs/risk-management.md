# Risk Management

This project is designed around paper trading and risk-control logic.

## Risk Controls

The webhook server validates every incoming signal.

It rejects signals if:

- webhook secret is invalid,
- symbol is not allowed,
- trade side is invalid,
- entry price is missing,
- stop-loss is missing,
- take-profit is missing,
- risk is too high,
- daily trade limit is reached,
- max open trade limit is reached,
- daily loss limit is reached,
- daily stop-loss limit is reached,
- risk/reward setup is invalid.

## Default Safety Settings

```env
PAPER_MODE=true
MAX_RISK_PERCENT=0.5
MAX_DAILY_TRADES=3
MAX_OPEN_TRADES=1
MAX_DAILY_LOSS_PERCENT=1.0
MAX_DAILY_STOP_LOSSES=2
SIGNAL_RISK_PERCENT=0.25
Purpose

The goal is to avoid uncontrolled automation and to design the system as if real risk controls were required.
