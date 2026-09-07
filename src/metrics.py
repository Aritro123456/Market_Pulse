"""Performance metrics for daily return series."""
import numpy as np


def annualized_return(returns):
    returns = returns.dropna()
    return (1 + returns).prod() ** (252 / len(returns)) - 1 if len(returns) else 0.0


def annualized_volatility(returns):
    return returns.dropna().std() * np.sqrt(252)


def sharpe_ratio(returns):
    returns = returns.dropna()
    volatility = returns.std()
    return returns.mean() / volatility * np.sqrt(252) if volatility else 0.0


def max_drawdown(cumulative):
    return (cumulative / cumulative.cummax() - 1).min()


def win_rate(returns):
    active = returns.dropna()[returns.dropna() != 0]
    return (active > 0).mean() if len(active) else 0.0


def summarize(name, returns):
    returns = returns.fillna(0)
    cumulative = (1 + returns).cumprod()
    return {"Strategy": name, "StrategyReturn": cumulative.iloc[-1] - 1,
            "AnnualizedReturn": annualized_return(returns),
            "AnnualizedVolatility": annualized_volatility(returns),
            "SharpeRatio": sharpe_ratio(returns), "MaximumDrawdown": max_drawdown(cumulative),
            "WinRate": win_rate(returns)}
