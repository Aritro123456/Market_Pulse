"""Build an offline market terminal from the local research pipeline."""
import json
from pathlib import Path
import pandas as pd
from plotly.offline import get_plotlyjs
from plotly.express import data as plotly_data
from metrics import summarize
from validation import monte_carlo, statistical_tests

ROOT = Path(__file__).resolve().parents[1]

def records(frame):
    return json.loads(frame.to_json(orient="records"))


def news_metadata():
    metadata = {}
    raw = ROOT / "data" / "raw"
    for folder in (raw / "alpha_vantage", raw / "alpha_vantage_historical"):
        for path in folder.glob("*.json"):
            try:
                feed = json.loads(path.read_text(encoding="utf-8")).get("feed", [])
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            for article in feed:
                if article.get("url"):
                    metadata[article["url"]] = {
                        "image": article.get("banner_image"), "summary": article.get("summary")}
    return metadata


def company_research(processed):
    data = pd.read_csv(processed / "validation_features.csv")
    data["Date"] = pd.to_datetime(data["Date"])
    metrics, walk, risk, tests = [], [], [], []
    strategies = {"Buy & Hold": "Return", "Momentum": "Momentum Net",
                  "Sentiment + Momentum": "Sentiment + Momentum Net", "Adaptive Risk": "Adaptive Risk Net"}
    for ticker, group in data.groupby("Ticker"):
        for name, column in strategies.items():
            metrics.append({"Ticker": ticker, **summarize(name, group[column])})
        for year in (2024, 2025, 2026):
            sample = group[group["Date"].dt.year == year]
            for name, column in list(strategies.items())[1:]:
                row = {"Ticker": ticker, **summarize(name, sample[column]), "TestYear": year,
                       "NumberOfTrades": sample[f"{name} Trade"].sum(),
                       "NewsDays": int((sample["News_Count"] > 0).sum())}
                walk.append(row)
        risk.append({"Ticker": ticker, **records(monte_carlo(group["Adaptive Risk Net"], simulations=1000))[0]})
        news = group[group["News_Count"] > 0]
        if (news["Sentiment"] > .2).sum() >= 2 and (news["Sentiment"] < -.2).sum() >= 2:
            tests.append({"Ticker": ticker, **records(statistical_tests(group))[0]})
        else:
            tests.append({"Ticker": ticker, "PValue": None})
    return metrics, walk, risk, tests

def build():
    processed = ROOT / "data" / "processed"
    market = pd.read_csv(ROOT / "data/raw/market_data.csv").sort_values(["Ticker", "Date"])
    signals = pd.read_csv(processed / "strategy_backtest.csv").sort_values("Date")
    news = pd.read_csv(processed / "news_sentiment.csv").sort_values("published_at", ascending=False)
    metadata = news_metadata()
    news["image"] = news["url"].map(lambda url: metadata.get(url, {}).get("image"))
    news["summary"] = news["url"].map(lambda url: metadata.get(url, {}).get("summary"))
    events = pd.read_csv(processed / "news_events.csv").sort_values("Date", ascending=False)
    company_metrics, company_walk, company_risk, company_tests = company_research(processed)
    countries = plotly_data.gapminder()[["country", "iso_alpha"]].drop_duplicates().reset_index(drop=True)
    payload = dict(prices=records(market.groupby("Ticker").tail(252)),
                   signals=records(signals.groupby("Ticker").tail(1)),
                   news=records(news.groupby("Ticker", sort=False).head(100)),
                   events=records(events.groupby("Ticker", sort=False).head(30)),
                   coverage=records(pd.read_csv(processed / "dataset_coverage.csv")),
                   metrics=records(pd.read_csv(processed / "strategy_metrics.csv")),
                   walk=records(pd.read_csv(processed / "walk_forward_results.csv")),
                   significance=records(pd.read_csv(processed / "sentiment_significance.csv")),
                   monte=records(pd.read_csv(processed / "monte_carlo_results.csv")),
                   companyMetrics=company_metrics, companyWalk=company_walk,
                   companyRisk=company_risk, companyTests=company_tests,
                   eventStudy=records(pd.read_csv(processed / "event_study_summary.csv")),
                   mapCountries=records(countries),
                   counts=dict(market=len(market), news=len(news), events=len(pd.read_csv(processed / "event_study_summary.csv"))),
                   asof=market.Date.max())
    template = (ROOT / "web/terminal.template.html").read_text(encoding="utf-8")
    html = template.replace("/*PLOTLY*/", get_plotlyjs()).replace("/*DATA*/", json.dumps(payload).replace("<", "\\u003c"))
    landing = (ROOT / "web/landing.template.html").read_text(encoding="utf-8")
    targets = [ROOT / "web/index.html", ROOT / "web/terminal.html"]
    targets[0].write_text(landing, encoding="utf-8")
    targets[1].write_text(html, encoding="utf-8")
    assert '/*DATA*/' not in html and len(payload['signals']) == 20
    print(f"Built {targets[0]} with {len(payload['signals'])} equities; prices through {payload['asof']}")

if __name__ == "__main__":
    build()
