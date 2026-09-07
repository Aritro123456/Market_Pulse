"""Test whether sentiment plus momentum relates to next-session returns."""
from pathlib import Path

import pandas as pd
from scipy.stats import ttest_ind


def classify_regime(row):
    if row["Volatility_20"] >= 0.40:
        return "High Volatility"
    if row["SMA_20"] > row["SMA_50"]:
        return "Bull Trend"
    if row["SMA_20"] < row["SMA_50"]:
        return "Bear Trend"
    return "Sideways"


def add_signals(features):
    data = features.copy()
    data["Regime"] = data.apply(classify_regime, axis=1)
    data["MomentumSignal"] = ((data["SMA_20"] > data["SMA_50"])
                              & (data["Momentum_5"] > 0)).astype(int)
    data["SentimentMomentumSignal"] = ((data["Sentiment"] > 0.20)
                                       & (data["Momentum_5"] > 0)
                                       & (data["RSI"] < 70)).astype(int)
    return data


def add_target(features):
    data = features.sort_values(["Ticker", "Date"]).copy()
    data["Next_Return"] = data.groupby("Ticker")["Close"].shift(-1) / data["Close"] - 1
    return data


def test_hypothesis(features):
    data = add_target(features)
    sample = data[(data["News_Count"] > 0) & data["Next_Return"].notna()].copy()
    sample["Signal"] = (sample["Sentiment"] > 0) & (sample["Momentum_5"] > 0)
    summary = (sample.groupby("Signal")["Next_Return"]
               .agg(Observations="count", MeanNextReturn="mean", MedianNextReturn="median",
                    WinRate=lambda values: (values > 0).mean()).reset_index())
    signal = sample.loc[sample["Signal"], "Next_Return"]
    other = sample.loc[~sample["Signal"], "Next_Return"]
    p_value = (ttest_ind(signal, other, equal_var=False, nan_policy="omit").pvalue
               if len(signal) >= 2 and len(other) >= 2 else float("nan"))
    return data, summary, p_value


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    processed = root / "data" / "processed"
    targeted, summary, p_value = test_hypothesis(pd.read_csv(processed / "model_features.csv"))
    targeted.to_csv(processed / "model_features_with_target.csv", index=False)
    summary.to_csv(processed / "hypothesis_results.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Welch t-test p-value: {p_value:.4f}")
