"""Download daily technology-stock prices from Yahoo Finance."""
from pathlib import Path

import pandas as pd
import yfinance as yf


TICKERS = ["NVDA", "AMD", "MSFT", "GOOGL", "META", "AAPL", "AMZN", "AVGO",
           "ORCL", "CRM", "ADBE", "INTC", "CSCO", "IBM", "QCOM", "TXN",
           "AMAT", "MU", "NOW", "TSLA", "QQQ"]
COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Ticker"]


def fetch_market_data(ticker, start="2015-01-01", end=None):
    if ticker not in TICKERS:
        raise ValueError(f"Unsupported ticker: {ticker}")
    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df.empty:
        raise ValueError(f"Yahoo Finance returned no data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    required = set(COLUMNS) - {"Ticker"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for {ticker}: {sorted(missing)}")
    df["Ticker"] = ticker
    return df[COLUMNS]


def fetch_all_tickers(start="2015-01-01", end=None):
    return pd.concat(
        [fetch_market_data(ticker, start, end) for ticker in TICKERS],
        ignore_index=True,
    )


if __name__ == "__main__":
    output = Path(__file__).parents[1] / "data" / "raw" / "market_data.csv"
    df = fetch_all_tickers()
    df.to_csv(output, index=False)
    print(df.head())
    print(df.shape)
    print(f"Saved {output}")
