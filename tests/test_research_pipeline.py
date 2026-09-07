"""Run: python tests/test_research_pipeline.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from backtest import run_backtests
from event_study import event_study

dates = pd.date_range("2026-01-01", periods=12)
rows = []
for ticker, base in [("NVDA", 100), ("QQQ", 200)]:
    for i, date in enumerate(dates):
        rows.append({"Date": date, "Ticker": ticker, "Close": base + i, "Return": .01,
                     "SMA_20": 2, "SMA_50": 1, "Momentum_5": 1, "Volatility_20": .2,
                     "RSI": 50, "Sentiment": .6 if ticker == "NVDA" and i == 5 else 0,
                     "News_Count": 1 if ticker == "NVDA" and i == 5 else 0})
features = pd.DataFrame(rows)
detail, portfolio, metrics = run_backtests(features)
assert detail.groupby("Ticker").head(1)["Momentum"].isna().all()
assert metrics["Strategy"].tolist() == ["Buy & Hold", "Momentum", "Sentiment + Momentum"]
windows, summary = event_study(features)
assert windows["Offset"].tolist() == list(range(-5, 6)) and len(summary) == 1
print("Research pipeline check passed: regimes, lagged signals, metrics and event window.")
