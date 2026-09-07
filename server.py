"""Serve MarketPulse and proxy Alpaca snapshots without exposing API keys."""
import json
import os
import time
import csv
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MARKET_FILE = ROOT / "data" / "processed" / "strategy_backtest.csv"
_cache = {"at": 0.0, "symbols": (), "data": {}}
_yahoo_cache = {"mtime": 0.0, "rows": {}}


def yahoo_rows():
    mtime = MARKET_FILE.stat().st_mtime
    if _yahoo_cache["mtime"] == mtime:
        return _yahoo_cache["rows"]
    rows = {}
    with MARKET_FILE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not all(row.get(column) for column in ("Close", "Return", "RSI", "MomentumSignal")):
                continue
            rows[row["Ticker"]] = {
                "Ticker": row["Ticker"], "YahooAsOf": row["Date"],
                "YahooClose": float(row["Close"]), "YahooReturn": float(row["Return"]),
                "Regime": row["Regime"], "RSI": float(row["RSI"]),
                "Momentum": "LONG" if float(row["MomentumSignal"]) else "CASH",
            }
    _yahoo_cache.update(mtime=mtime, rows=rows)
    return rows


ALLOWED = set(yahoo_rows())


def alpaca_client():
    load_dotenv(ROOT / ".env")
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Alpaca credentials are missing from .env")
    return StockHistoricalDataClient(key, secret)


def snapshots(symbols):
    key = tuple(sorted(symbols))
    if _cache["symbols"] == key and time.time() - _cache["at"] < 10:
        return _cache["data"]
    raw = alpaca_client().get_stock_snapshot(
        StockSnapshotRequest(symbol_or_symbols=list(key), feed=DataFeed.IEX)
    )
    data = {}
    for symbol, snap in raw.items():
        trade, quote, day, previous = snap.latest_trade, snap.latest_quote, snap.daily_bar, snap.previous_daily_bar
        price = getattr(trade, "price", None)
        if price is None and quote:
            price = (quote.bid_price + quote.ask_price) / 2
        data[symbol] = {
            "price": price,
            "bid": getattr(quote, "bid_price", None),
            "ask": getattr(quote, "ask_price", None),
            "timestamp": str(getattr(trade or quote or day, "timestamp", "")),
            "open": getattr(day, "open", None),
            "high": getattr(day, "high", None),
            "low": getattr(day, "low", None),
            "volume": getattr(day, "volume", None),
            "previous_close": getattr(previous, "close", None),
        }
    _cache.update(at=time.time(), symbols=key, data=data)
    return data


def combined_market(symbols):
    yahoo, live = yahoo_rows(), snapshots(symbols)
    rows = []
    for symbol in symbols:
        row = dict(yahoo[symbol])
        snapshot = live.get(symbol, {})
        row.update(IEXLast=snapshot.get("price"), IEXTimestamp=snapshot.get("timestamp"),
                   IEXPreviousClose=snapshot.get("previous_close"))
        rows.append(row)
    return {"sources": {"live": "Alpaca IEX", "historical": "Yahoo Finance"},
            "snapshots": live, "rows": rows}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/snapshots", "/api/market-table"}:
            return super().do_GET()
        requested = parse_qs(parsed.query).get("symbols", [""])[0].upper().split(",")
        symbols = [symbol for symbol in dict.fromkeys(requested) if symbol in ALLOWED]
        if not symbols:
            return self.send_json(400, {"error": "No supported symbols requested"})
        try:
            payload = (combined_market(symbols) if parsed.path == "/api/market-table"
                       else {"source": "Alpaca IEX", "snapshots": snapshots(symbols)})
            self.send_json(200, payload)
        except Exception as exc:
            self.send_json(503, {"error": str(exc)})

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    address = (os.getenv("HOST", "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"), port)
    print(f"MarketPulse: http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, Handler).serve_forever()
