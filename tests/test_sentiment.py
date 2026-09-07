"""Run: python tests/test_sentiment.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.sentiment import aggregate_daily, build_events, score_headlines


def fake_classifier(texts, **_):
    labels = ["positive", "negative", "neutral"]
    return [{"label": labels[index], "score": 0.9} for index, _ in enumerate(texts)]


news = pd.DataFrame({
    "article_id": ["a", "b", "c"], "Ticker": ["NVDA"] * 3,
    "title": ["growth", "loss", "unchanged"],
    "published_at": ["2026-09-01T01:00:00Z", "2026-09-01T02:00:00Z",
                     "2026-09-02T01:00:00Z"],
    "ticker_relevance": [1.0, .5, 1.0],
    "topics": ["earnings", "earnings", "technology"],
})
scored = score_headlines(news, fake_classifier)
daily = aggregate_daily(scored)
assert scored["SentimentScore"].tolist() == [1, -1, 0]
assert daily["DailySentiment"].round(3).tolist() == [0.333, 0.0]
assert daily["ArticleCount"].tolist() == [2, 1]
events = build_events(scored)
assert set(events["EventCategory"]) == {"EARNINGS", "OTHER"}
print("FinBERT check passed: label mapping and daily aggregation.")
