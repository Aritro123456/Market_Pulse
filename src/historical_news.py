"""Resumable, rate-limited Alpha Vantage historical news collection."""
import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    from .news_data import COLUMNS, _download, parse_news
except ImportError:
    from news_data import COLUMNS, _download, parse_news

TICKERS = ["NVDA", "AMD", "MSFT", "GOOGL", "META", "AAPL", "AMZN", "TSLA", "AVGO", "ORCL"]


def quarter_windows(start="2022-01-01", end="2026-10-01"):
    dates = pd.date_range(start, end, freq="QS").tolist() + [pd.Timestamp(end)]
    return [(dates[i].date(), (dates[i + 1] - pd.Timedelta(minutes=1)).date())
            for i in range(len(dates) - 1)]


def key(ticker, start, end):
    return f"{ticker}|{start}|{end}"


def split_window(start, end):
    midpoint = start + (end - start) // 2
    return [(start, midpoint), (midpoint + timedelta(days=1), end)]


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def pending_tasks(state):
    pending = []

    def add(ticker, start, end):
        entry = state.get(key(ticker, start, end), {})
        if entry.get("status") == "complete":
            return
        if entry.get("status") == "split":
            for child_start, child_end in entry["children"]:
                add(ticker, pd.Timestamp(child_start).date(), pd.Timestamp(child_end).date())
        else:
            pending.append((ticker, start, end))

    for ticker in TICKERS:
        for start, end in quarter_windows():
            add(ticker, start, end)
    counts = {ticker: sum(item.get("count", 0) for item in state.values()
                          if item.get("ticker") == ticker and item.get("status") == "complete")
              for ticker in TICKERS}
    return sorted(pending, key=lambda task: (counts[task[0]], task[1], task[0]))


def build_dataset(cache_dir, state, existing=None):
    frames = [pd.read_csv(existing)] if existing and existing.exists() else []
    for item in state.values():
        if item.get("status") != "complete":
            continue
        path = cache_dir / item["file"]
        data = json.loads(path.read_text(encoding="utf-8"))
        frames.append(parse_news(data, item["ticker"], min_relevance=.40))
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values("ticker_relevance", ascending=False)
    return result.drop_duplicates(["Ticker", "url"]).drop_duplicates(["Ticker", "title_normalized"])


def collect(max_requests=20, pause=15, session=None, sleep=time.sleep):
    root = Path(__file__).parents[1]
    cache_dir = root / "data" / "raw" / "alpha_vantage_historical"
    state_file = cache_dir / "collection_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("Set ALPHA_VANTAGE_API_KEY before historical collection")
    tasks, requests_used = pending_tasks(state), 0
    while tasks and requests_used < max_requests:
        ticker, start, end = tasks.pop(0)
        if requests_used:
            sleep(pause)
        kwargs = {"time_from": f"{start:%Y%m%d}T0000", "time_to": f"{end:%Y%m%d}T2359",
                  "sort": "EARLIEST"}
        call_kwargs = {"session": session, "sleep": sleep} if session else {"sleep": sleep}
        try:
            data = _download(ticker, api_key, **call_kwargs, **kwargs)
        except Exception as exc:
            state[key(ticker, start, end)] = {"status": "error", "error": str(exc),
                                               "ticker": ticker, "updated_at": datetime.utcnow().isoformat()}
            save_json(state_file, state)
            break
        requests_used += 1
        window_key = key(ticker, start, end)
        if len(data["feed"]) >= 1000 and (end - start).days > 31:
            children = split_window(start, end)
            state[window_key] = {"status": "split", "ticker": ticker,
                                 "children": [[str(a), str(b)] for a, b in children]}
            tasks = [(ticker, a, b) for a, b in children] + tasks
        else:
            filename = f"{ticker}_{start}_{end}.json"
            save_json(cache_dir / filename, data)
            state[window_key] = {"status": "complete", "ticker": ticker,
                                 "count": len(data["feed"]), "file": filename}
        save_json(state_file, state)
        print(f"{ticker} {start}..{end}: {len(data['feed'])} articles", flush=True)
    output = root / "data" / "raw" / "historical_news.csv"
    build_dataset(cache_dir, state, root / "data" / "raw" / "news_data.csv").to_csv(output, index=False)
    print(f"Used {requests_used}/{max_requests} requests; run again later to resume")
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--pause", type=int, default=15)
    args = parser.parse_args()
    collect(args.max_requests, args.pause)
