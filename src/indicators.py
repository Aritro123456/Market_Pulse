"""Technical indicators calculated independently for each ticker."""
from pathlib import Path

import numpy as np
import pandas as pd


def calculate_rsi(series, period=14):
    if period < 1:
        raise ValueError("RSI period must be positive")
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.mask((avg_gain == 0) & (avg_loss == 0), 50).mask((avg_gain > 0) & (avg_loss == 0), 100)


def add_indicators(df):
    required = {"Date", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="raise")
    df["Close"] = pd.to_numeric(df["Close"], errors="raise")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="raise")
    if df.empty or df[["Close", "Volume"]].isna().any().any() or (df["Close"] <= 0).any() or (df["Volume"] < 0).any():
        raise ValueError("Close must be positive and Volume must be non-negative")
    if df["Date"].duplicated().any():
        raise ValueError("Duplicate dates within ticker")
    df = df.sort_values("Date")
    df["Return"] = df["Close"].pct_change(fill_method=None)
    for window in (10, 20, 50):
        df[f"SMA_{window}"] = df["Close"].rolling(window).mean()
    df["Momentum_5"] = df["Close"].pct_change(5, fill_method=None)
    df["Momentum_20"] = df["Close"].pct_change(20, fill_method=None)
    df["Volatility_20"] = df["Return"].rolling(20).std() * np.sqrt(252)
    df["Volume_Change"] = df["Volume"].pct_change(fill_method=None)
    df["RSI"] = calculate_rsi(df["Close"])
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df


def add_indicators_by_ticker(df):
    if "Ticker" not in df.columns or df["Ticker"].isna().any():
        raise ValueError("Ticker is required")
    if df.duplicated(["Ticker", "Date"]).any():
        raise ValueError("Duplicate ticker/date rows")
    return pd.concat(
        [add_indicators(group) for _, group in df.groupby("Ticker", sort=False)],
        ignore_index=True,
    ).sort_values(["Ticker", "Date"]).reset_index(drop=True)


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    source = root / "data" / "raw" / "market_data.csv"
    output = root / "data" / "processed" / "market_features.csv"
    result = add_indicators_by_ticker(pd.read_csv(source))
    result.to_csv(output, index=False)
    print(result.groupby("Ticker").size())
    print(f"Saved {len(result)} rows to {output}")
