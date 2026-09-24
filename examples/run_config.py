"""Run the Jev agent using a config.json for url and goal.

Usage:
  uv run --env-file .env python examples/run_config.py
  uv run --env-file .env python examples/run_config.py --config path/to/config.json

config.json shape:
  {
    "url": "https://...",
    "goal": ["A narrow goal", "An optional second, ordered goal"]
  }
`goal` may also be a single string.
"""

import argparse
import json
from pathlib import Path

from jev_ultrafast import Agent

parser = argparse.ArgumentParser()
parser.add_argument(
    "--config",
    default=str(Path(__file__).resolve().parent.parent / "config.json"),
    help="Path to config.json (defaults to the repo-root config.json).",
)
args = parser.parse_args()

config = json.loads(Path(args.config).read_text())

url = config["url"]
goal = config["goal"]
if isinstance(goal, str):
    goal = [goal]
if not url or not goal:
    raise SystemExit("config.json must set a non-empty 'url' and 'goal'.")

with Agent(url, goal) as agent:
    for state in agent.run():
        print(f"{state['elapsed_ms']:>5} ms  {len(state['history'])} actions  {state['status']}")
    print(state["page"]["url"])
