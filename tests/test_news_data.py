"""Run: python tests/test_news_data.py"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.news_data import COLUMNS, fetch_news

article = {
    "title": "NVIDIA revenue rises", "url": "https://example.com/a",
    "source": "Example", "time_published": "20260901T120000",
    "overall_sentiment_score": 0.4, "overall_sentiment_label": "Bullish",
    "ticker_sentiment": [{"ticker": "NVDA", "ticker_sentiment_score": "0.35",
                           "ticker_sentiment_label": "Bullish", "relevance_score": "0.9"}],
    "topics": [{"topic": "Technology"}],
}

with tempfile.TemporaryDirectory() as directory:
    limited = Mock(status_code=200, headers={})
    limited.json.return_value = {"Note": "rate limit"}
    limited.raise_for_status.return_value = None
    success = Mock(status_code=200, headers={})
    success.json.return_value = {"feed": [article, article]}
    success.raise_for_status.return_value = None
    session = Mock()
    session.get.side_effect = [limited, success]
    sleeps = []
    result = fetch_news("NVDA", directory, "test-key", session=session, sleep=sleeps.append)
    assert list(result.columns) == COLUMNS and len(result) == 1
    assert result.loc[0, "ticker_sentiment_score"] == 0.35
    assert sleeps == [15] and session.get.call_count == 2
    assert json.loads((Path(directory) / "NVDA.json").read_text())["feed"]
    assert len(fetch_news("NVDA", directory, session=Mock())) == 1

print("Alpha Vantage check passed: retry, cache, parsing and deduplication.")
