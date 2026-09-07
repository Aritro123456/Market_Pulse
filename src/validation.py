"""Robustness checks for MarketPulse strategies."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, ttest_ind

try:
    from .metrics import summarize
    from .strategy import add_signals
except ImportError:
    from metrics import summarize
    from strategy import add_signals

STRATEGIES = ["Momentum", "Sentiment + Momentum", "Adaptive Risk"]


def prepare(features):
    data = add_signals(features).sort_values(["Ticker", "Date"]).copy()
    data["Date"] = pd.to_datetime(data["Date"])
    groups = data.groupby("Ticker", group_keys=False)
    for horizon in (1, 3, 5, 10):
        data[f"Return_{horizon}D"] = groups["Close"].shift(-horizon) / data["Close"] - 1
    for column, output in (("Sentiment", "Sentiment_Shock_Z"),
                           ("News_Count", "NewsIntensity_Z"), ("Volume", "Volume_Z"),
                           ("Return", "Return_Z")):
        mean = groups[column].transform(lambda x: x.rolling(20, min_periods=10).mean())
        std = groups[column].transform(lambda x: x.rolling(20, min_periods=10).std())
        data[output] = ((data[column] - mean) / std).replace([np.inf, -np.inf], np.nan)
    data["EventScore"] = ((data["Sentiment_Shock_Z"].abs() >= 1.5).astype(int) * 2
                          + (data["NewsIntensity_Z"] >= 1).astype(int)
                          + (data["Volume_Z"].abs() >= 1).astype(int)
                          + (data["Return_Z"].abs() >= 1).astype(int))
    data["MarketEvent"] = (data["Has_News"] == 1) & (data["EventScore"] >= 3)
    data["AdaptiveSignal"] = np.select(
        [data["Regime"].eq("Bull Trend"), data["Regime"].eq("High Volatility")],
        [data["MomentumSignal"], data["SentimentMomentumSignal"]], default=0)
    data["RiskWeight"] = (0.20 / data["Volatility_20"]).clip(upper=1).fillna(0)
    return data


def strategy_returns(data, cost_bps=10, slippage_bps=5):
    data = data.copy()
    signals = {"Momentum": "MomentumSignal", "Sentiment + Momentum": "SentimentMomentumSignal",
               "Adaptive Risk": "AdaptiveSignal"}
    for name, signal in signals.items():
        position = data.groupby("Ticker")[signal].shift(1).fillna(0)
        if name == "Adaptive Risk":
            position *= data.groupby("Ticker")["RiskWeight"].shift(1).fillna(0)
        trade = position.groupby(data["Ticker"]).diff().abs().fillna(position.abs())
        data[f"{name} Gross"] = position * data["Return"]
        data[f"{name} Net"] = data[f"{name} Gross"] - trade * (cost_bps + slippage_bps) / 10_000
        data[f"{name} Trade"] = trade
    return data


def walk_forward(data):
    rows = []
    for year in (2024, 2025, 2026):
        test = data[data["Date"].dt.year == year]
        for name in STRATEGIES:
            result = summarize(name, test.groupby("Date")[f"{name} Net"].mean())
            result.update({"TrainThrough": year - 1, "TestYear": year,
                           "NumberOfTrades": test[f"{name} Trade"].sum(),
                           "NewsDays": int((test["News_Count"] > 0).sum())})
            rows.append(result)
    return pd.DataFrame(rows)


def statistical_tests(data):
    news = data[(data["News_Count"] > 0) & data["Return_1D"].notna()]
    positive = news.loc[news["Sentiment"] > .2, "Return_1D"]
    negative = news.loc[news["Sentiment"] < -.2, "Return_1D"]
    test = ttest_ind(positive, negative, equal_var=False, nan_policy="omit")
    return pd.DataFrame([{"PositiveN": len(positive), "PositiveMean": positive.mean(),
                          "NegativeN": len(negative), "NegativeMean": negative.mean(),
                          "Difference": positive.mean() - negative.mean(),
                          "TStatistic": test.statistic, "PValue": test.pvalue}])


def information_coefficients(data):
    rows = []
    for feature in ["Sentiment", "Momentum_5", "RSI", "Volume_Z", "Sentiment_Shock_Z"]:
        sample = data[data["News_Count"] > 0] if "Sentiment" in feature else data
        row = {"Feature": feature}
        for horizon in (1, 3, 5, 10):
            valid = sample[[feature, f"Return_{horizon}D"]].dropna()
            if len(valid) < 3 or valid[feature].nunique() < 2 or valid[f"Return_{horizon}D"].nunique() < 2:
                ic, p = np.nan, np.nan
            else:
                ic, p = spearmanr(valid[feature], valid[f"Return_{horizon}D"])
            row.update({f"IC_{horizon}D": ic, f"P_{horizon}D": p, f"N_{horizon}D": len(valid)})
        rows.append(row)
    return pd.DataFrame(rows)


def regime_metrics(data):
    rows = []
    for regime, group in data.groupby("Regime"):
        for name in STRATEGIES:
            result = summarize(name, group.groupby("Date")[f"{name} Net"].mean())
            result["Regime"] = regime
            rows.append(result)
    return pd.DataFrame(rows)


def monte_carlo(returns, simulations=1000, seed=42):
    values = returns.dropna().to_numpy()
    paths = np.random.default_rng(seed).choice(values, (simulations, len(values)), replace=True)
    cumulative = np.cumprod(1 + paths, axis=1)
    drawdowns = (cumulative / np.maximum.accumulate(cumulative, axis=1) - 1).min(axis=1)
    terminal = cumulative[:, -1] - 1
    return pd.DataFrame([{"Simulations": simulations, "MedianTerminalReturn": np.median(terminal),
                          "P05TerminalReturn": np.quantile(terminal, .05),
                          "P95TerminalReturn": np.quantile(terminal, .95),
                          "ProbabilityOfLoss": (terminal < 0).mean(),
                          "MedianMaxDrawdown": np.median(drawdowns)}])


def stress_test(data):
    rows = []
    for cost in (5, 10, 20, 50):
        for threshold in (.1, .2, .3, .4):
            for window in (5, 20):
                signal = ((data["Sentiment"] > threshold) & (data[f"Momentum_{window}"] > 0)
                          & (data["RSI"] < 70)).astype(int)
                position = signal.groupby(data["Ticker"]).shift(1).fillna(0)
                trade = position.groupby(data["Ticker"]).diff().abs().fillna(position.abs())
                returns = (position * data["Return"] - trade * (cost + 5) / 10_000).groupby(data["Date"]).mean()
                result = summarize("Sentiment + Momentum", returns)
                result.update({"CostBps": cost, "SlippageBps": 5,
                               "SentimentThreshold": threshold, "MomentumWindow": window})
                rows.append(result)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    output = root / "data" / "processed"
    prepared = prepare(pd.read_csv(output / "model_features.csv"))
    data = strategy_returns(prepared[prepared["Ticker"] != "QQQ"].copy())
    data.to_csv(output / "validation_features.csv", index=False)
    walk_forward(data).to_csv(output / "walk_forward_results.csv", index=False)
    statistical_tests(data).to_csv(output / "sentiment_significance.csv", index=False)
    information_coefficients(data).to_csv(output / "information_coefficients.csv", index=False)
    regime_metrics(data).to_csv(output / "regime_strategy_metrics.csv", index=False)
    stress_test(data).to_csv(output / "stress_test_results.csv", index=False)
    adaptive = data.groupby("Date")["Adaptive Risk Net"].mean()
    monte_carlo(adaptive).to_csv(output / "monte_carlo_results.csv", index=False)
    print(walk_forward(data).to_string(index=False))
