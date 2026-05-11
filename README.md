# 团子赛跑开源蒙特卡洛模型

这是一个用于《鸣潮》团子赛跑的蒙特卡洛模拟模型。它会把比赛规则写成代码，重复模拟大量比赛，输出每个团子的冠军率、晋级率、平均名次、标准差和保本赔率。

这个版本把“固定环境”和“团子技能”拆开：

- 环境固定：32 格赛道、绿色箭头、红色箭头、漩涡、布大王、堆叠、携带、随机行动顺序。
- 技能可输入：在 `skills_b_group.json` 里替换团子名称和 `skill` 即可。
- 上半场：随机初始堆叠，每轮行动顺序随机，跑完第一圈结算。
- 下半场：输入上半场结束位置，继续跑第二圈。

## 文件说明

- `engine.py`：核心模拟引擎，包含赛道规则、堆叠/携带、机关、布大王、技能执行和统计输出。
- `run_first_half.py`：上半场预测入口。从第 0 格开始，随机初始堆叠，模拟第一圈。
- `run_second_half.py`：下半场预测入口。读取上半场结束后的当前位置，继续模拟第二圈。
- `skills_b_group.json`：当前 B 组 6 个团子的比赛配置示例。
- `known_beans.json`：目前已知的 A 组、B 组共 12 个团子及其技能 ID，可作为换配置时的技能库。
- `example_second_half_scores.json`：下半场位置输入示例。
- `README.md`：使用说明。

## 快速开始

需要 Python 3.10 或以上版本，不依赖第三方库。

进入目录：

```powershell
cd tanzu_open_model
```

运行 B 组上半场：

```powershell
python run_first_half.py --config skills_b_group.json --trials 100000 --seed 42
```

参数说明：

- `--config`：团子配置文件。
- `--trials`：模拟次数。建议正式预测用 `100000` 或 `200000`。
- `--seed`：随机种子。固定种子可以复现实验结果，不传也可以。

输出字段说明：

- `champion`：冠军率。
- `qualify`：晋级率，也就是 6 进 4 中进入前四的概率。
- `avg_rank`：平均名次，越低越好。
- `std`：名次标准差，越低越稳定。
- `r1` 到 `r6`：获得对应名次的概率。
- `break_even_odds`：保本黑马值。实际黑马值高于它，才更可能有正期望。

## 位置输入约定

用小数表示同格堆叠高度：

- `30.2` 表示在第 30 格较底部。
- `30.1` 表示在第 30 格较顶部。

例如“陆·赫斯顶着绯雪在第 30 格，所以绯雪第四，陆·赫斯第五”：

```json
{"陆·赫斯团子": 30.2, "绯雪团子": 30.1}
```

运行下半场示例：

```powershell
python run_second_half.py --config skills_b_group.json --scores-file example_second_half_scores.json --trials 100000 --seed 42
```

## 如何更换团子和技能

推荐流程：

1. 打开 `known_beans.json`，找到你要预测的 6 个团子。
2. 复制它们的 `name` 和 `skill`。
3. 新建或修改一个配置文件，例如 `skills_my_group.json`。
4. 把 `beans` 数组替换成你选择的 6 个团子。
5. 用 `--config skills_my_group.json` 运行模型。

配置文件最小示例：

```json
{
  "track_len": 32,
  "qualify_count": 4,
  "include_budawang": true,
  "budawang_start_round": 3,
  "beans": [
    {"name": "千咲团子", "skill": "min_roll_bonus_2"},
    {"name": "琳奈团子", "skill": "double_60_or_stop_20"},
    {"name": "爱弥斯团子", "skill": "teleport_after_midpoint_once"},
    {"name": "守岸人团子", "skill": "only_2_or_3"},
    {"name": "珂莱塔团子", "skill": "double_steps_28"},
    {"name": "莫宁团子", "skill": "cycle_3_2_1"}
  ]
}
```

如果某个团子没有技能，可以写：

```json
{"name": "绯雪团子", "skill": null}
```

## 已支持的技能 ID

- `double_steps_28`：28% 概率以骰子的双倍点数前进。
- `only_2_or_3`：骰子只会掷出 2 或 3。
- `teleport_after_midpoint_once`：每场一次，经过赛程中点后，若前方存在其他非布大王团子，传送到最近团子顶端。
- `double_60_or_stop_20`：每回合 60% 概率双倍点数移动，20% 概率无法移动，其余正常移动。
- `cycle_3_2_1`：点数固定按 3/2/1 循环。
- `min_roll_bonus_2`：若投出的结果为本轮所有点数最小之一，额外前进 2 格。
- `candy_device`：触发推进装置时额外前进 3 格；触发阻碍装置时额外后退 1 格。
- `sun_spirit_slow_two`：每轮标记前方相邻最多两个团子，使其本回合少前进 1 格。
- `double_same_roll`：若投出和上一次相同的点数，额外前进 2 格。
- `last_place_60_forward_2`：若自身移动结束后处于最后一名，本场剩余回合有 60% 概率额外前进 2 格。
- `blessing_50_forward_1`：50% 概率额外前进 1 格。

## 环境规则

- 赛道共 32 格，第 0 格既是起点也是终点。
- 绿色箭头在第 `3, 11, 16, 22` 格。
- 红色箭头在第 `10, 28` 格。
- 漩涡在第 `6, 20` 格。
- 团子移动结束落到已有团子的格子上，会叠到该格最上方。
- 团子移动时，会携带自己上方所有团子一起移动。
- 同一堆同时到达终点时，按从上到下结算名次。
- 每轮行动顺序随机。
- 上半场开局时，6 个团子全部在第 0 格，初始堆叠顺序随机。
- 下半场基于上半场结束位置继续行动，看谁先完成第二圈。

## 作者的话

C 组团子出来之后，作者会更新加入 C 组团子技能。
