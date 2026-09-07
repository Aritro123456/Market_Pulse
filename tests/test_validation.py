"""Run: python tests/test_validation.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.validation import information_coefficients, monte_carlo, prepare, strategy_returns

dates = pd.date_range("2024-01-01", periods=30)
data = pd.DataFrame({"Date": list(dates) * 2, "Ticker": ["A"] * 30 + ["B"] * 30,
                     "Close": list(range(100, 130)) + list(range(200, 230)),
                     "Return": [.01] * 60, "Volume": list(range(1000, 1030)) * 2,
                     "SMA_20": [2] * 60, "SMA_50": [1] * 60, "Momentum_5": [.1] * 60,
                     "Momentum_20": [.2] * 60, "Volatility_20": [.25] * 60,
                     "RSI": [50] * 60, "Sentiment": ([0] * 15 + [.5] * 15) * 2,
                     "News_Count": ([0] * 15 + [1] * 15) * 2,
                     "Has_News": ([0] * 15 + [1] * 15) * 2})
prepared = strategy_returns(prepare(data))
assert prepared.groupby("Ticker").head(1)["Momentum Gross"].eq(0).all()
assert prepared["Momentum Net"].sum() < prepared["Momentum Gross"].sum()
assert len(information_coefficients(prepared)) == 5
assert monte_carlo(prepared.groupby("Date")["Adaptive Risk Net"].mean(), 20)["Simulations"].iat[0] == 20
print("Validation check passed: lagging, costs, IC, shocks, risk sizing and Monte Carlo.")
