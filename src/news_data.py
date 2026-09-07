"""Download Alpha Vantage news once, then reuse its JSON cache."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.alphavantage.co/query"
TICKERS = ["NVDA", "AMD", "MSFT", "META", "GOOGL"]
COLUMNS = ["article_id", "Ticker", "title", "url", "source", "published_at",
           "sentiment_score", "sentiment_label", "ticker_sentiment_score",
           "ticker_sentiment_label", "ticker_relevance", "relevance_tier",
           "title_normalized", "topics", "collected_at"]


def _retry_delay(response, attempt):
    value = response.headers.get("Retry-After")
    if value and value.isdigit():
        return max(15, int(value))
    if value:
        try:
            return max(15, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            pass
    return 15 * 2 ** attempt


def _download(ticker, api_key, session=requests, sleep=time.sleep, **filters):
    params = {"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": 1000,
              "sort": "LATEST", "apikey": api_key}
    params.update({key: value for key, value in filters.items() if value is not None})
    for attempt in range(4):
        response = session.get(BASE_URL, params=params, timeout=30)
        if response.status_code == 429:
            if attempt < 3:
                sleep(_retry_delay(response, attempt))
                continue
            response.raise_for_status()
        response.raise_for_status()
        try:
            data = response.json()
        except (requests.JSONDecodeError, ValueError) as exc:
            raise ValueError("Alpha Vantage returned invalid JSON") from exc
        message = data.get("Note") or data.get("Information")
        if message:
            if attempt < 3:
                sleep(_retry_delay(response, attempt))
                continue
            raise RuntimeError(f"Alpha Vantage rate limit: {message}")
        if "Error Message" in data:
            raise RuntimeError(f"Alpha Vantage error: {data['Error Message']}")
        if not isinstance(data.get("feed"), list):
            raise ValueError("Alpha Vantage response has no news feed")
        return data
    raise RuntimeError("Alpha Vantage request failed")


def normalize_title(title):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", title.lower())).strip()


def parse_news(data, ticker, min_relevance=0.70):
    collected_at = datetime.now(timezone.utc).isoformat()
    rows, seen_urls, seen_titles = [], set(), set()
    for article in data["feed"]:
        title, url = article.get("title"), article.get("url")
        normalized = normalize_title(title) if title else ""
        published = pd.to_datetime(article.get("time_published"), format="%Y%m%dT%H%M%S",
                                   utc=True, errors="coerce")
        if not title or not url or pd.isna(published) or url in seen_urls or normalized in seen_titles:
            continue
        match = next((item for item in article.get("ticker_sentiment", [])
                      if item.get("ticker") == ticker), {})
        relevance = pd.to_numeric(match.get("relevance_score"), errors="coerce")
        if pd.isna(relevance) or relevance < min_relevance:
            continue
        seen_urls.add(url)
        seen_titles.add(normalized)
        tier = "HIGH" if relevance >= .8 else "MEDIUM" if relevance >= .6 else "LOW"
        rows.append({
            "article_id": hashlib.sha256(url.encode()).hexdigest(), "Ticker": ticker,
            "title": title, "url": url, "source": article.get("source"),
            "published_at": published,
            "sentiment_score": pd.to_numeric(article.get("overall_sentiment_score"), errors="coerce"),
            "sentiment_label": article.get("overall_sentiment_label"),
            "ticker_sentiment_score": pd.to_numeric(match.get("ticker_sentiment_score"), errors="coerce"),
            "ticker_sentiment_label": match.get("ticker_sentiment_label"),
            "ticker_relevance": relevance, "relevance_tier": tier,
            "title_normalized": normalized,
            "topics": ", ".join(topic.get("topic", "") for topic in article.get("topics", [])),
            "collected_at": collected_at,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def fetch_news(ticker, cache_dir=None, api_key=None, force=False,
               session=requests, sleep=time.sleep):
    ticker = ticker.upper()
    if ticker not in TICKERS:
        raise ValueError(f"Unsupported ticker: {ticker}")
    cache_dir = Path(cache_dir or Path(__file__).parents[1] / "data" / "raw" / "alpha_vantage")
    cache_file = cache_dir / f"{ticker}.json"
    if cache_file.exists() and not force:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise RuntimeError("Set ALPHA_VANTAGE_API_KEY before downloading news")
        try:
            data = _download(ticker, api_key, session, sleep)
            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary = cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            temporary.replace(cache_file)
        except (requests.RequestException, RuntimeError, ValueError):
            if not cache_file.exists():
                raise
            print(f"Refresh failed for {ticker}; using its existing local cache", flush=True)
            data = json.loads(cache_file.read_text(encoding="utf-8"))

    return parse_news(data, ticker)


def fetch_all_tickers(force=False, pause=15, sleep=time.sleep, **kwargs):
    frames, live_calls = [], 0
    cache_dir = Path(kwargs.get("cache_dir") or Path(__file__).parents[1] / "data" / "raw" / "alpha_vantage")
    for ticker in TICKERS:
        needs_live_call = force or not (cache_dir / f"{ticker}.json").exists()
        if needs_live_call and live_calls:
            sleep(pause)
        try:
            frames.append(fetch_news(ticker, force=force, sleep=sleep, **kwargs))
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            print(f"Skipped {ticker}: {exc}", flush=True)
        live_calls += needs_live_call
    if not frames:
        raise RuntimeError("No news was available from the API or local cache")
    return pd.concat(frames, ignore_index=True).drop_duplicates(["Ticker", "url"])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="refresh all five local caches")
    args = parser.parse_args()
    output = Path(__file__).parents[1] / "data" / "raw" / "news_data.csv"
    result = fetch_all_tickers(force=args.refresh)
    result.to_csv(output, index=False)
    print(result.groupby("Ticker").size())
    print(f"Saved {len(result)} articles to {output}")
