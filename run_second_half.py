from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine import load_config, print_report, run_second_half_from_scores, simulate


def parse_scores(raw: str) -> dict[str, float]:
    # 推荐输入 JSON，如：
    # {"陆·赫斯团子":30.2,"绯雪团子":30.1}
    return {str(k): float(v) for k, v in json.loads(raw).items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="团子赛跑下半场预测")
    parser.add_argument("--config", default="skills_b_group.json")
    parser.add_argument("--scores", default=None, help="JSON dict: name -> score, e.g. 30.2 means lower than 30.1")
    parser.add_argument("--scores-file", default=None, help="JSON file path for name -> score")
    parser.add_argument("--trials", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.scores and not args.scores_file:
        raise SystemExit("provide --scores or --scores-file")

    cfg = load_config(Path(args.config))
    scores = parse_scores(args.scores) if args.scores else parse_scores(Path(args.scores_file).read_text(encoding="utf-8"))
    report = simulate(
        run_second_half_from_scores,
        cfg,
        trials=args.trials,
        seed=args.seed,
        scores=scores,
    )
    print_report(report)


if __name__ == "__main__":
    main()
