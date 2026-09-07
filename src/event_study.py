"""Measure QQQ-adjusted returns around extreme company-news days."""
from pathlib import Path

import pandas as pd


def select_events(data, tail=0.25):
    news = data[(data["Ticker"] != "QQQ") & (data["News_Count"] > 0)].copy()
    low, high = news["Sentiment"].quantile([tail, 1 - tail])
    news["EventType"] = ""
    news.loc[(news["Sentiment"] < 0) & (news["Sentiment"] <= low), "EventType"] = "Strong Negative"
    news.loc[(news["Sentiment"] > 0) & (news["Sentiment"] >= high), "EventType"] = "Strong Positive"
    return news[news["EventType"] != ""]


def event_study(features, headlines=None, radius=5):
    data = features.copy()
    data["Date"] = pd.to_datetime(data["Date"]).dt.normalize()
    qqq = data.loc[data["Ticker"] == "QQQ", ["Date", "Return"]].rename(columns={"Return": "QQQReturn"})
    events = select_events(data)
    headline_map = {}
    if headlines is not None:
        headlines = headlines.copy()
        headlines["Date"] = pd.to_datetime(headlines["published_at"], utc=True).dt.tz_localize(None).dt.normalize()
        chosen = headlines.sort_values("ticker_relevance").drop_duplicates(["Ticker", "Date"], keep="last")
        headline_map = chosen.set_index(["Ticker", "Date"])["title"].to_dict()
    rows = []
    for event in events.itertuples():
        series = (data[data["Ticker"] == event.Ticker][["Date", "Return"]]
                  .merge(qqq, on="Date").sort_values("Date").reset_index(drop=True))
        matches = series.index[series["Date"] == event.Date]
        if len(matches) != 1 or matches[0] < radius or matches[0] + radius >= len(series):
            continue
        window = series.iloc[matches[0] - radius:matches[0] + radius + 1].copy()
        window["Offset"] = range(-radius, radius + 1)
        window["AbnormalReturn"] = window["Return"] - window["QQQReturn"]
        window["CAR"] = window["AbnormalReturn"].cumsum()
        for point in window.itertuples():
            rows.append({"Ticker": event.Ticker, "EventDate": event.Date,
                         "EventType": event.EventType,
                         "Headline": headline_map.get((event.Ticker, event.Date)),
                         "Sentiment": event.Sentiment, "NewsCount": event.News_Count,
                         "Offset": point.Offset, "AbnormalReturn": point.AbnormalReturn,
                         "CAR": point.CAR})
    windows = pd.DataFrame(rows)
    if windows.empty:
        return windows, pd.DataFrame()
    car_name = f"CAR_Minus{radius}_Plus{radius}"
    summary = (windows[windows["Offset"] == radius].rename(columns={"CAR": car_name})
               [["Ticker", "EventDate", "EventType", "Headline", "Sentiment", "NewsCount", car_name]])
    return windows, summary


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    processed = root / "data" / "processed"
    source = processed / "model_features.csv"
    windows, summary = event_study(pd.read_csv(source), pd.read_csv(processed / "news_sentiment.csv"))
    windows.to_csv(processed / "event_study_windows.csv", index=False)
    summary.to_csv(processed / "event_study_summary.csv", index=False)
    aggregate = (windows.groupby(["EventType", "Offset"], as_index=False)
                 .agg(MeanAbnormalReturn=("AbnormalReturn", "mean"), MeanCAR=("CAR", "mean"),
                      Events=("EventDate", "nunique")))
    aggregate.to_csv(processed / "event_study_aggregate.csv", index=False)
    market = (pd.read_csv(source).query("Ticker != 'QQQ'").groupby("Ticker", as_index=False)
              .agg(MarketRows=("Date", "size"), MatchedArticles=("News_Count", "sum"),
                   NewsDays=("Has_News", "sum")))
    news_source = root / "data" / "raw" / "historical_news.csv"
    raw_news = pd.read_csv(news_source if news_source.exists() else root / "data" / "raw" / "news_data.csv")
    raw_news["Year"] = pd.to_datetime(raw_news["published_at"], utc=True).dt.year
    articles = raw_news.groupby("Ticker").size().rename("RelevantArticles")
    years = raw_news.groupby("Ticker")["Year"].nunique().rename("YearsCovered")
    strong = summary.groupby("Ticker").size().rename("StrongEvents")
    coverage = market.join(articles, on="Ticker").join(years, on="Ticker").join(strong, on="Ticker").fillna(0)
    coverage["EventConcentration"] = coverage["StrongEvents"] / max(coverage["StrongEvents"].sum(), 1)
    coverage["CoverageScore"] = (
        (coverage["RelevantArticles"] / 400).clip(upper=1) * 30
        + (coverage["NewsDays"] / 150).clip(upper=1) * 25
        + (coverage["YearsCovered"] / 5).clip(upper=1) * 25
        + (coverage["StrongEvents"] / 20).clip(upper=1) * 20
        - ((coverage["EventConcentration"] - .25).clip(lower=0) * 100)
    ).clip(lower=0).round(1)
    coverage["CoverageLabel"] = pd.cut(coverage["CoverageScore"], [-1, 49, 74, 100],
                                        labels=["INSUFFICIENT", "MODERATE", "GOOD"])
    coverage.to_csv(processed / "dataset_coverage.csv", index=False)
    (raw_news.pivot_table(index="Ticker", columns="Year", values="article_id", aggfunc="count",
                          fill_value=0).to_csv(processed / "news_coverage_by_year.csv"))
    print(summary.groupby("EventType").size())
    print(f"Saved {len(summary)} events and {len(windows)} event-window rows")
