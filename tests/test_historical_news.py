"""Run: python tests/test_historical_news.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.historical_news import key, pending_tasks, split_window

children = split_window(date(2022, 1, 1), date(2022, 3, 31))
assert children[0][0] == date(2022, 1, 1) and children[1][1] == date(2022, 3, 31)
state = {key("NVDA", date(2022, 1, 1), date(2022, 3, 31)):
         {"status": "complete", "ticker": "NVDA", "count": 100}}
tasks = pending_tasks(state)
assert ("NVDA", date(2022, 1, 1), date(2022, 3, 31)) not in tasks
assert tasks[0][0] != "NVDA"
print("Historical collector check passed: windows, state resume and coverage priority.")
