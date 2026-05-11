from __future__ import annotations

import argparse
from pathlib import Path

from engine import load_config, print_report, run_first_half, simulate


def main() -> None:
    parser = argparse.ArgumentParser(description="团子赛跑上半场预测")
    parser.add_argument("--config", default="skills_b_group.json")
    parser.add_argument("--trials", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    report = simulate(run_first_half, cfg, trials=args.trials, seed=args.seed)
    print_report(report)


if __name__ == "__main__":
    main()
