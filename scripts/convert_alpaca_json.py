#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Alpaca-style JSON arrays to JSONL.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = json.loads(args.input.read_text())
    if not isinstance(rows, list):
        raise ValueError("Expected the input file to contain a JSON array")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
