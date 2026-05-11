from __future__ import annotations

import dataclasses
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


TRACK_LEN = 32
FIRST_LAP_TARGET = 32
SECOND_LAP_TARGET = 64
QUALIFY_COUNT = 4
DICE = (1, 2, 3)
BUDDAWANG_DICE = (1, 2, 3, 4, 5, 6)
BUDDAWANG = "布大王团子"

TILES = {
    3: "green_arrow",
    6: "vortex",
    10: "red_arrow",
    11: "green_arrow",
    16: "green_arrow",
    20: "vortex",
    22: "green_arrow",
    28: "red_arrow",
}


@dataclasses.dataclass(frozen=True)
class BeanConfig:
    name: str
    skill: str | None = None


@dataclasses.dataclass
class RaceConfig:
    beans: list[BeanConfig]
    track_len: int = TRACK_LEN
    tiles: dict[int, str] = dataclasses.field(default_factory=lambda: dict(TILES))
    qualify_count: int = QUALIFY_COUNT
    include_budawang: bool = True
    budawang_start_round: int = 3

    @property
    def names(self) -> list[str]:
        return [bean.name for bean in self.beans]

    @property
    def skill_by_name(self) -> dict[str, str | None]:
        return {bean.name: bean.skill for bean in self.beans}


@dataclasses.dataclass
class RaceState:
    pos: dict[str, int]
    progress: dict[str, int]
    stacks: dict[int, list[str]]
    finished: list[str] = dataclasses.field(default_factory=list)
    round_no: int = 1
    last_roll: dict[str, int] = dataclasses.field(default_factory=dict)
    roll_count: dict[str, int] = dataclasses.field(default_factory=dict)
    used_once: set[str] = dataclasses.field(default_factory=set)
    crossed_midpoint: set[str] = dataclasses.field(default_factory=set)
    met_budawang: set[str] = dataclasses.field(default_factory=set)
    budawang_pos: int = 0


def load_config(path: str | Path) -> RaceConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return RaceConfig(
        beans=[BeanConfig(item["name"], item.get("skill")) for item in raw["beans"]],
        track_len=int(raw.get("track_len", TRACK_LEN)),
        tiles={int(k): v for k, v in raw.get("tiles", TILES).items()},
        qualify_count=int(raw.get("qualify_count", QUALIFY_COUNT)),
        include_budawang=bool(raw.get("include_budawang", True)),
        budawang_start_round=int(raw.get("budawang_start_round", 3)),
    )


def initial_first_half(cfg: RaceConfig, rng: random.Random) -> RaceState:
    top_to_bottom = cfg.names[:]
    rng.shuffle(top_to_bottom)
    bottom_to_top = list(reversed(top_to_bottom))
    return RaceState(
        pos={name: 0 for name in cfg.names},
        progress={name: 0 for name in cfg.names},
        stacks={0: bottom_to_top},
        budawang_pos=0,
    )


def state_from_position_scores(cfg: RaceConfig, scores: dict[str, float]) -> RaceState:
    by_tile: dict[int, list[tuple[int, str]]] = defaultdict(list)
    pos: dict[str, int] = {}
    progress: dict[str, int] = {}
    for name, score in scores.items():
        tile = int(score)
        dec = int(round((score - tile) * 10))
        pos[name] = tile % cfg.track_len
        progress[name] = tile
        by_tile[pos[name]].append((dec, name))

    stacks: dict[int, list[str]] = {}
    for tile, items in by_tile.items():
        # 用户约定：30.2 表示更底，30.1 表示更顶，所以底->顶按小数大到小。
        stacks[tile] = [name for _, name in sorted(items, reverse=True)]

    return RaceState(pos=pos, progress=progress, stacks=stacks, budawang_pos=0)


def active(cfg: RaceConfig, state: RaceState) -> list[str]:
    return [name for name in cfg.names if name not in state.finished]


def stack_at(state: RaceState, pos: int) -> list[str]:
    return state.stacks.get(pos, [])


def current_rank_key(state: RaceState, name: str) -> tuple[int, int]:
    stack = stack_at(state, state.pos[name])
    height = stack.index(name) if name in stack else -1
    return (-state.progress[name], -height)


def remove_names(state: RaceState, pos: int, names: list[str]) -> None:
    remaining = [name for name in state.stacks.get(pos, []) if name not in names]
    if remaining:
        state.stacks[pos] = remaining
    elif pos in state.stacks:
        del state.stacks[pos]


def put_top(state: RaceState, pos: int, group_bottom_to_top: list[str]) -> None:
    if not group_bottom_to_top:
        return
    if BUDDAWANG in group_bottom_to_top:
        group_bottom_to_top = [BUDDAWANG] + [n for n in group_bottom_to_top if n != BUDDAWANG]
    state.stacks.setdefault(pos, []).extend(group_bottom_to_top)
    for name in group_bottom_to_top:
        state.pos[name] = pos
    if BUDDAWANG in group_bottom_to_top:
        state.budawang_pos = pos


def carried_group(state: RaceState, name: str) -> list[str]:
    stack = stack_at(state, state.pos[name])
    return stack[stack.index(name) :]


def finish_group(state: RaceState, group: list[str], target: int) -> None:
    for name in reversed(group):
        if name != BUDDAWANG and name not in state.finished and state.progress.get(name, -999) >= target:
            state.finished.append(name)


def move_group(
    cfg: RaceConfig,
    state: RaceState,
    group: list[str],
    steps: int,
    rng: random.Random,
    *,
    direction: int,
    target: int,
    apply_tiles: bool = True,
) -> None:
    if not group or steps == 0:
        return
    old_pos = state.pos[group[0]]
    remove_names(state, old_pos, group)
    delta = direction * steps

    for name in group:
        if name == BUDDAWANG or name in state.finished:
            continue
        state.progress[name] += delta

    new_pos = (old_pos + delta) % cfg.track_len
    if direction > 0 and any(
        name != BUDDAWANG and name not in state.finished and state.progress[name] >= target
        for name in group
    ):
        finish_group(state, group, target)
        remain = [name for name in group if name == BUDDAWANG or name not in state.finished]
        put_top(state, 0, remain)
        return

    put_top(state, new_pos, group)
    if apply_tiles:
        apply_tile(cfg, state, group, rng, target=target)


def apply_tile(cfg: RaceConfig, state: RaceState, group: list[str], rng: random.Random, *, target: int) -> None:
    pos = state.pos[group[0]]
    tile = cfg.tiles.get(pos)
    if tile == "green_arrow":
        move_group(cfg, state, group, 1, rng, direction=1, target=target, apply_tiles=False)
    elif tile == "red_arrow":
        move_group(cfg, state, group, 1, rng, direction=-1, target=target, apply_tiles=False)
    elif tile == "vortex":
        affected = [name for name in stack_at(state, pos) if name in group]
        remove_names(state, pos, affected)
        if BUDDAWANG in affected:
            others = [n for n in affected if n != BUDDAWANG]
            rng.shuffle(others)
            put_top(state, pos, [BUDDAWANG] + others)
        else:
            rng.shuffle(affected)
            put_top(state, pos, affected)


def roll_for_skill(skill: str | None, state: RaceState, name: str, rng: random.Random) -> int:
    if skill == "only_2_or_3":
        return rng.choice((2, 3))
    if skill == "cycle_3_2_1":
        cycle = (3, 2, 1)
        count = state.roll_count.get(name, 0)
        return cycle[count % 3]
    return rng.choice(DICE)


def round_rolls(cfg: RaceConfig, state: RaceState, rng: random.Random) -> dict[str, int]:
    return {
        name: roll_for_skill(cfg.skill_by_name.get(name), state, name, rng)
        for name in active(cfg, state)
    }


def step_multiplier(skill: str | None, rng: random.Random) -> float:
    if skill == "double_steps_28":
        return 2 if rng.random() < 0.28 else 1
    if skill == "double_60_or_stop_20":
        r = rng.random()
        if r < 0.20:
            return 0
        if r < 0.80:
            return 2
    return 1


def extra_steps_after_roll(
    cfg: RaceConfig,
    state: RaceState,
    name: str,
    roll: int,
    round_roll_map: dict[str, int],
    rng: random.Random,
) -> int:
    skill = cfg.skill_by_name.get(name)
    if skill == "min_roll_bonus_2" and roll == min(round_roll_map.values()):
        return 2
    if skill == "double_same_roll" and state.last_roll.get(name) == roll:
        return 2
    if skill == "blessing_50_forward_1" and rng.random() < 0.5:
        return 1
    return 0


def maybe_midpoint_teleport(cfg: RaceConfig, state: RaceState, name: str) -> None:
    if cfg.skill_by_name.get(name) != "teleport_after_midpoint_once":
        return
    key = f"{name}:midpoint"
    if key in state.used_once or state.progress[name] < cfg.track_len // 2:
        return
    ahead = [
        other
        for other in active(cfg, state)
        if other != name and state.progress[other] > state.progress[name]
    ]
    if not ahead:
        return
    target = min(ahead, key=lambda other: state.progress[other] - state.progress[name])
    remove_names(state, state.pos[name], [name])
    state.pos[name] = state.pos[target]
    state.progress[name] = state.progress[target]
    put_top(state, state.pos[target], [name])
    state.used_once.add(key)


def maybe_sun_spirit_penalties(cfg: RaceConfig, state: RaceState) -> dict[str, int]:
    penalties: dict[str, int] = defaultdict(int)
    for name in active(cfg, state):
        if cfg.skill_by_name.get(name) != "sun_spirit_slow_two":
            continue
        own = current_rank_key(state, name)
        ahead = [other for other in active(cfg, state) if other != name and current_rank_key(state, other) < own]
        ahead.sort(key=lambda other: current_rank_key(state, other), reverse=True)
        for other in ahead[:2]:
            penalties[other] += 1
    return penalties


def maybe_last_place_bonus(cfg: RaceConfig, state: RaceState, name: str, rng: random.Random, target: int) -> None:
    if cfg.skill_by_name.get(name) != "last_place_60_forward_2":
        return
    key = f"{name}:last_place_60_forward_2"
    if key in state.used_once:
        return
    last = max(active(cfg, state), key=lambda n: current_rank_key(state, n))
    if last == name and rng.random() < 0.6:
        state.used_once.add(key)
        move_group(cfg, state, carried_group(state, name), 2, rng, direction=1, target=target)


def move_budawang(cfg: RaceConfig, state: RaceState, rng: random.Random, target: int) -> None:
    if BUDDAWANG not in state.pos:
        state.pos[BUDDAWANG] = state.budawang_pos
        state.stacks.setdefault(state.budawang_pos, []).insert(0, BUDDAWANG)
    group = carried_group(state, BUDDAWANG)
    move_group(cfg, state, group, rng.choice(BUDDAWANG_DICE), rng, direction=-1, target=target)
    if not active(cfg, state):
        return
    last = max(active(cfg, state), key=lambda n: current_rank_key(state, n))
    if state.pos[last] != state.budawang_pos:
        remove_names(state, state.budawang_pos, [BUDDAWANG])
        state.budawang_pos = 0
        state.pos[BUDDAWANG] = 0
        state.stacks.setdefault(0, []).insert(0, BUDDAWANG)


def play_until(cfg: RaceConfig, state: RaceState, rng: random.Random, *, target: int, stop_at: int) -> list[str]:
    while len(state.finished) < stop_at:
        rolls = round_rolls(cfg, state, rng)
        penalties = maybe_sun_spirit_penalties(cfg, state)
        order = active(cfg, state)
        rng.shuffle(order)
        for name in order:
            if name in state.finished:
                continue
            skill = cfg.skill_by_name.get(name)
            roll = rolls[name]
            state.roll_count[name] = state.roll_count.get(name, 0) + 1
            multiplier = step_multiplier(skill, rng)
            steps = int(max(0, roll * multiplier))
            if steps > 0:
                steps = max(1, steps - penalties.get(name, 0))
                steps += extra_steps_after_roll(cfg, state, name, roll, rolls, rng)
                landing = (state.pos[name] + steps) % cfg.track_len
                steps += apply_candy_arrow_bonus(cfg, state, name, landing)
                move_group(cfg, state, carried_group(state, name), max(0, steps), rng, direction=1, target=target)
                maybe_midpoint_teleport(cfg, state, name)
                if name not in state.finished:
                    maybe_last_place_bonus(cfg, state, name, rng, target)
            state.last_roll[name] = roll
            if len(state.finished) >= stop_at:
                break
        if cfg.include_budawang and state.round_no >= cfg.budawang_start_round and len(state.finished) < stop_at:
            move_budawang(cfg, state, rng, target)
        state.round_no += 1
    return state.finished[:stop_at]


def apply_candy_arrow_bonus(cfg: RaceConfig, state: RaceState, name: str, landing: int) -> int:
    if cfg.skill_by_name.get(name) != "candy_device":
        return 0
    tile = cfg.tiles.get(landing)
    if tile == "green_arrow":
        return 3
    if tile == "red_arrow":
        return -1
    return 0


def run_first_half(cfg: RaceConfig, rng: random.Random) -> list[str]:
    return play_until(cfg, initial_first_half(cfg, rng), rng, target=FIRST_LAP_TARGET, stop_at=len(cfg.names))


def run_second_half_from_scores(cfg: RaceConfig, scores: dict[str, float], rng: random.Random) -> list[str]:
    return play_until(cfg, state_from_position_scores(cfg, scores), rng, target=SECOND_LAP_TARGET, stop_at=len(cfg.names))


def simulate(fn, cfg: RaceConfig, trials: int, seed: int | None = None, **kwargs) -> dict[str, Any]:
    rng = random.Random(seed)
    rank_counts = {rank: Counter() for rank in range(1, len(cfg.names) + 1)}
    ranks_by_name: dict[str, list[int]] = defaultdict(list)
    orders = Counter()
    for _ in range(trials):
        result = fn(cfg, rng=rng, **kwargs)
        orders[tuple(result)] += 1
        for rank, name in enumerate(result, start=1):
            rank_counts[rank][name] += 1
            ranks_by_name[name].append(rank)

    rows = []
    for name in cfg.names:
        ranks = ranks_by_name[name]
        row = {
            "name": name,
            "champion": rank_counts[1][name] / trials,
            "qualify": sum(rank_counts[i][name] for i in range(1, cfg.qualify_count + 1)) / trials,
            "avg_rank": mean(ranks),
            "std": pstdev(ranks),
        }
        for rank in range(1, len(cfg.names) + 1):
            row[f"r{rank}"] = rank_counts[rank][name] / trials
        p = row["champion"]
        row["break_even_odds"] = (1 - (1 - p) * 0.8) / p if p > 0 else None
        rows.append(row)
    return {"trials": trials, "rows": rows, "orders": orders.most_common(10)}


def print_report(report: dict[str, Any]) -> None:
    print(f"trials: {report['trials']}")
    print("name\tchampion\tqualify\tavg_rank\tstd\tr1\tr2\tr3\tr4\tr5\tr6\tbreak_even_odds")
    for row in sorted(report["rows"], key=lambda r: r["avg_rank"]):
        print(
            "\t".join(
                [
                    row["name"],
                    f"{row['champion']:.4f}",
                    f"{row['qualify']:.4f}",
                    f"{row['avg_rank']:.4f}",
                    f"{row['std']:.4f}",
                    f"{row['r1']:.4f}",
                    f"{row['r2']:.4f}",
                    f"{row['r3']:.4f}",
                    f"{row['r4']:.4f}",
                    f"{row['r5']:.4f}",
                    f"{row['r6']:.4f}",
                    "" if row["break_even_odds"] is None else f"{row['break_even_odds']:.4f}",
                ]
            )
        )
    print("\nmost_common_orders")
    for order, count in report["orders"]:
        print(f"{count / report['trials']:.4f}\t" + " > ".join(order))
