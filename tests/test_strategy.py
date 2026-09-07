"""Run: python tests/test_strategy.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.strategy import add_target, test_hypothesis

features = pd.DataFrame({
    "Ticker": ["A", "A", "A", "B", "B", "B"],
    "Date": ["2026-01-01", "2026-01-02", "2026-01-03"] * 2,
    "Close": [100, 110, 99, 200, 180, 198], "News_Count": [1] * 6,
    "Sentiment": [1, -1, 0, 1, -1, 0], "Momentum_5": [1, -1, 0, 1, -1, 0],
})
targeted = add_target(features)
assert targeted.groupby("Ticker").tail(1)["Next_Return"].isna().all()
_, summary, p_value = test_hypothesis(features)
assert summary["Observations"].sum() == 4 and p_value >= 0
print("Hypothesis check passed: ticker-safe targets, signal groups and t-test.")
