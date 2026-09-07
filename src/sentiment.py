"""Score cached headlines with FinBERT and aggregate daily sentiment."""
from pathlib import Path
import hashlib

import pandas as pd

LABEL_MAP = {"positive": 1, "neutral": 0, "negative": -1}
EVENT_TERMS = {
    "EARNINGS": ("earnings", "quarterly results", "profit", "revenue"),
    "GUIDANCE": ("guidance", "forecast", "outlook"),
    "M&A": ("acquisition", "acquire", "merger", "takeover"),
    "REGULATORY": ("regulator", "regulation", "antitrust", "ftc", "sec "),
    "LEGAL": ("lawsuit", "court", "settlement", "legal"),
    "MANAGEMENT": ("ceo", "cfo", "executive", "director resign"),
    "PRODUCT": ("launch", "product", "chip", "iphone", "azure", "cloud"),
    "ANALYST_RATING": ("upgrade", "downgrade", "price target", "analyst"),
    "MACRO": ("inflation", "interest rate", "federal reserve", "economy"),
}


def score_headlines(news, classifier, batch_size=32):
    news = news.copy()
    results = classifier(news["title"].fillna("").tolist(), batch_size=batch_size,
                         truncation=True, max_length=512)
    labels = [result["label"].lower() for result in results]
    if unknown := set(labels) - LABEL_MAP.keys():
        raise ValueError(f"Unexpected FinBERT labels: {sorted(unknown)}")
    news["FinBERTLabel"] = labels
    news["FinBERTConfidence"] = [result["score"] for result in results]
    news["SentimentScore"] = [LABEL_MAP[label] for label in labels]
    return news


def aggregate_daily(scored):
    data = scored.copy()
    data["Date"] = pd.to_datetime(data["published_at"], utc=True).dt.date
    data["WeightedSentiment"] = data["SentimentScore"] * data["ticker_relevance"]
    daily = (data.groupby(["Ticker", "Date"], as_index=False)
             .agg(WeightedSentiment=("WeightedSentiment", "sum"),
                  RelevanceSum=("ticker_relevance", "sum"),
                  ArticleCount=("article_id", "count"),
                  MeanConfidence=("FinBERTConfidence", "mean"),
                  MeanRelevance=("ticker_relevance", "mean")))
    daily["DailySentiment"] = daily["WeightedSentiment"] / daily["RelevanceSum"]
    return daily.drop(columns=["WeightedSentiment", "RelevanceSum"])


def classify_event(title, topics=""):
    text = f"{title} {topics}".lower()
    return next((category for category, terms in EVENT_TERMS.items()
                 if any(term in text for term in terms)), "OTHER")


def build_events(scored):
    data = scored.copy()
    data["Date"] = pd.to_datetime(data["published_at"], utc=True).dt.date
    data["EventCategory"] = [classify_event(title, topics)
                             for title, topics in zip(data["title"], data["topics"].fillna(""))]
    data["WeightedSentiment"] = data["SentimentScore"] * data["ticker_relevance"]
    grouped = (data.groupby(["Ticker", "Date", "EventCategory"], as_index=False)
               .agg(ArticleCount=("article_id", "count"), RelevanceSum=("ticker_relevance", "sum"),
                    WeightedSentiment=("WeightedSentiment", "sum"),
                    MeanRelevance=("ticker_relevance", "mean")))
    grouped["EventSentiment"] = grouped["WeightedSentiment"] / grouped["RelevanceSum"]
    representative = data.loc[data.groupby(["Ticker", "Date", "EventCategory"])["ticker_relevance"].idxmax(),
                              ["Ticker", "Date", "EventCategory", "title"]]
    grouped = grouped.merge(representative, on=["Ticker", "Date", "EventCategory"])
    grouped["EventID"] = [hashlib.sha256(f"{ticker}|{date}|{category}".encode()).hexdigest()
                          for ticker, date, category in zip(grouped["Ticker"], grouped["Date"],
                                                            grouped["EventCategory"])]
    # ponytail: same-category stories on one company-day form one event; use semantic clustering if this ceiling matters.
    return grouped.drop(columns=["WeightedSentiment", "RelevanceSum"]).rename(columns={"title": "RepresentativeHeadline"})


if __name__ == "__main__":
    from transformers import pipeline

    root = Path(__file__).parents[1]
    output = root / "data" / "processed"
    historical = root / "data" / "raw" / "historical_news.csv"
    news = pd.read_csv(historical if historical.exists() else root / "data" / "raw" / "news_data.csv")
    classifier = pipeline("text-classification", model="ProsusAI/finbert")
    scored = score_headlines(news, classifier)
    scored.to_csv(output / "news_sentiment.csv", index=False)
    aggregate_daily(scored).to_csv(output / "daily_sentiment.csv", index=False)
    build_events(scored).to_csv(output / "news_events.csv", index=False)
    print(scored.groupby(["Ticker", "FinBERTLabel"]).size())
    print(f"Saved {len(scored)} scored headlines")
