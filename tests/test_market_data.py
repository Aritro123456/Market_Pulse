"""Run: python tests/test_market_data.py"""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.market_data import COLUMNS, fetch_market_data

sample = pd.DataFrame(
    {"Open": [10], "High": [12], "Low": [9], "Close": [11], "Volume": [100]},
    index=pd.to_datetime(["2026-09-01"]),
)
sample.index.name = "Date"
with patch("src.market_data.yf.download", return_value=sample):
    result = fetch_market_data("NVDA")
assert list(result.columns) == COLUMNS and result.loc[0, "Ticker"] == "NVDA"
print("Market data check passed.")
