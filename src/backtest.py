"""Compare buy-and-hold with two long-or-cash strategies."""
from pathlib import Path

import pandas as pd

try:
    from .metrics import summarize
    from .strategy import add_signals
except ImportError:  # direct `python src/backtest.py` execution
    from metrics import summarize
    from strategy import add_signals


def run_backtests(features):
    data = add_signals(features).sort_values(["Ticker", "Date"])
    data = data[data["Ticker"] != "QQQ"].copy()
    data["Buy & Hold"] = data["Return"]
    data["Momentum"] = data.groupby("Ticker")["MomentumSignal"].shift(1) * data["Return"]
    data["Sentiment + Momentum"] = (data.groupby("Ticker")["SentimentMomentumSignal"].shift(1)
                                     * data["Return"])
    strategies = ["Buy & Hold", "Momentum", "Sentiment + Momentum"]
    portfolio = data.groupby("Date", as_index=False)[strategies].mean()
    metrics = pd.DataFrame([summarize(name, portfolio[name]) for name in strategies])
    for name in strategies:
        portfolio[f"{name} Cumulative"] = (1 + portfolio[name].fillna(0)).cumprod()
    return data, portfolio, metrics


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    processed = root / "data" / "processed"
    detail, portfolio, metrics = run_backtests(pd.read_csv(processed / "model_features.csv"))
    detail.to_csv(processed / "strategy_backtest.csv", index=False)
    portfolio.to_csv(processed / "portfolio_backtest.csv", index=False)
    metrics.to_csv(processed / "strategy_metrics.csv", index=False)
    print(metrics.to_string(index=False))
