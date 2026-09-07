"""Run: python tests/test_indicators.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.indicators import add_indicators_by_ticker, calculate_rsi

dates = pd.date_range("2026-01-01", periods=60)
raw = pd.concat([
    pd.DataFrame({"Date": dates, "Close": np.arange(1, 61), "Volume": 100, "Ticker": "UP"}),
    pd.DataFrame({"Date": dates, "Close": np.arange(60, 0, -1), "Volume": 200, "Ticker": "DOWN"}),
])
result = add_indicators_by_ticker(raw)
for ticker in ("UP", "DOWN"):
    first = result[result.Ticker == ticker].iloc[0]
    assert pd.isna(first.Return) and pd.isna(first.Volume_Change)
assert calculate_rsi(pd.Series(range(20))).iloc[-1] == 100
assert result[result.Ticker == "UP"].RSI.iloc[-1] == 100
assert result[result.Ticker == "DOWN"].RSI.iloc[-1] == 0
assert result[result.Ticker == "UP"].Volatility_20.iloc[-1] >= 0
print("Indicator checks passed: ticker isolation, RSI, returns, volume and volatility.")
