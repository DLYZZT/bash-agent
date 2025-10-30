#!/usr/bin/env python3
import sys

from src.agent import Agent
from src.config import load_config
from src.cli import console


def main(argv: list[str]) -> None:
    config = load_config(console)
    agent = Agent(config)
    try:
        agent.run(argv)
    finally:
        agent.shutdown()


if __name__ == "__main__":
    main(sys.argv)
