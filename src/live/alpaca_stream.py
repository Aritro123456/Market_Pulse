"""Print live IEX minute bars; stop with Ctrl+C."""
import os
import threading

from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream
from dotenv import load_dotenv

SYMBOLS = ["NVDA", "AMD", "MSFT", "GOOGL", "META"]
bars_received = 0


async def handle_bar(bar):
    global bars_received
    bars_received += 1
    print(f"{bar.symbol} | O:{bar.open} H:{bar.high} L:{bar.low} "
          f"C:{bar.close} V:{bar.volume}", flush=True)


def run(duration=None):
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("Add Alpaca paper credentials to .env")
    stream = StockDataStream(api_key, secret_key, feed=DataFeed.IEX)
    stream.subscribe_bars(handle_bar, *SYMBOLS)
    print("Starting MarketPulse IEX stream. Bars appear while the feed is active; Ctrl+C stops it.")
    timer = threading.Timer(duration, stream.stop) if duration else None
    if timer:
        timer.start()
    stream.run()
    if timer:
        timer.cancel()
    print(f"Stream stopped cleanly; bars received: {bars_received}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, help="stop automatically after this many seconds")
    run(parser.parse_args().seconds)
