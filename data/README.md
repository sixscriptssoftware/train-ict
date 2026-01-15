# Backtest Data (TradingView Export)

This project can backtest using CSVs exported from TradingView.

## Export from TradingView

1. Open the chart for your instrument (e.g., EURUSD).
2. Set the timeframe you want (e.g., 15m).
3. Export chart data to CSV (TradingView UI varies by version).
4. Save the CSV into this folder.

## Required filenames

The backtest script expects files named:

- `EURUSD_1d.csv`
- `EURUSD_1h.csv`
- `EURUSD_15m.csv`

(Adjust the symbol/timeframes if you change them in `scripts/run_backtest.py`.)

## CSV format expectations

The CSV must include OHLC columns (case-insensitive):

- `open`, `high`, `low`, `close`

A time column is required and can be one of:

- `time`, `date`, `datetime`, `timestamp`

If there is no explicit time column, the first column will be treated as the timestamp index.
