"""Merge technical market features with daily news sentiment."""
from pathlib import Path

import pandas as pd

FEATURE_COLUMNS = ["Date", "Ticker", "Close", "Return", "Volume", "SMA_20", "SMA_50",
                   "Momentum_5", "Momentum_20", "Volatility_20", "RSI", "MACD",
                   "Has_News", "News_Count", "Sentiment", "MeanRelevance"]


def build_features(market, sentiment):
    market, sentiment = market.copy(), sentiment.copy()
    market["Date"] = pd.to_datetime(market["Date"]).dt.normalize()
    sentiment["Date"] = pd.to_datetime(sentiment["Date"]).dt.normalize()
    sentiment = sentiment.rename(columns={"ArticleCount": "News_Count",
                                          "DailySentiment": "Sentiment"})
    merged = market.merge(sentiment[["Date", "Ticker", "News_Count", "Sentiment", "MeanRelevance"]],
                          on=["Date", "Ticker"], how="left", validate="many_to_one")
    merged["Has_News"] = merged["Sentiment"].notna().astype(int)
    merged["News_Count"] = merged["News_Count"].fillna(0).astype(int)
    merged["Sentiment"] = merged["Sentiment"].fillna(0.0)
    merged["MeanRelevance"] = merged["MeanRelevance"].fillna(0.0)
    return merged[FEATURE_COLUMNS]


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    processed = root / "data" / "processed"
    features = build_features(pd.read_csv(processed / "market_features.csv"),
                              pd.read_csv(processed / "daily_sentiment.csv"))
    output = processed / "model_features.csv"
    features.to_csv(output, index=False)
    print(features.groupby("Ticker").size())
    print(f"Saved {len(features)} feature rows to {output}")
