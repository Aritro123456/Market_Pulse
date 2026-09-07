"""Run: python tests/test_features.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.features import FEATURE_COLUMNS, build_features

market = pd.DataFrame({
    "Date": ["2026-09-01", "2026-09-02"], "Ticker": ["NVDA", "NVDA"],
    "Close": [100, 101], "Return": [0, .01], "Volume": [10, 11],
    "SMA_20": [90, 91], "SMA_50": [80, 81], "Momentum_5": [.1, .2],
    "Momentum_20": [.2, .3], "Volatility_20": [.3, .4], "RSI": [50, 55],
    "MACD": [1, 2],
})
sentiment = pd.DataFrame({"Date": ["2026-09-01"], "Ticker": ["NVDA"],
                          "ArticleCount": [3], "DailySentiment": [.5], "MeanRelevance": [.9]})
result = build_features(market, sentiment)
assert list(result.columns) == FEATURE_COLUMNS and len(result) == len(market)
assert result[["News_Count", "Sentiment"]].values.tolist() == [[3, .5], [0, 0.0]]
assert result["Has_News"].tolist() == [1, 0]
print("Feature merge check passed: matched news and zero-filled missing news.")
