"""Verify Alpaca paper credentials without placing an order."""
import os

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")
if not api_key or not secret_key:
    raise ValueError("Add Alpaca paper credentials to .env")

account = TradingClient(api_key, secret_key, paper=True).get_account()
print("Connection successful")
print("Account status:", account.status)
print("Buying power:", account.buying_power)
print("Portfolio value:", account.portfolio_value)
