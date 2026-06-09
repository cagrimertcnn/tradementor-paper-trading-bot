# Backtesting and Optimization

The project includes historical testing scripts to evaluate strategy behavior before running it in live paper mode.

## Backtest Script

`backtest_filtered.py` downloads historical Binance candlestick data and simulates paper trades using the same signal logic.

It reports:

- total closed trades,
- winning trades,
- losing trades,
- win rate,
- estimated account PnL,
- recent trade results.

## Optimizer Script

`optimizer.py` tests multiple combinations of:

- SMA fast length,
- SMA slow length,
- ATR stop multiplier,
- risk/reward target,
- long RSI range,
- short RSI range.

The optimizer ranks configurations by estimated PnL, win rate, trade count and max losing streak.

## Important Note

Backtesting can overfit past data. Optimized parameters must still be validated with forward paper testing before any live use.
