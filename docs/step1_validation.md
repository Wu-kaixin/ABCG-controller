# Step 1 验收报告

**最终结论：CLOSED（冻结的 Step 1 范围）**

本报告只引用当前分支重新运行且可追溯的结果。机器 gate 与冻结矩阵定义见 `experiments/acceptance_manifest.yaml`；每个运行目录含 config/input/source/task hash、严格 JSON、无 pickle 轨迹、规划历史和原子状态。

## 冻结信息

| 项目 | 值 |
|---|---|
| 验证日期 | 2026-09-19 |
| 分支 | `codex/step1-closure` |
| 验证代码 commit | `c9d751684f3981c4539efdf430fd9f4cbf953e19` |
| 验证启动时工作树 | clean（`dirty=false`） |
| manifest SHA-256 | `b87a4735aad4aff4040e069c6db64020d2c7ba641351000599b895bd823c3eef` |
| source SHA-256 | `945f842557b277ae6e516eec528282d0a1fe4be4f586d8eafa0da3bf6195a408` |
| 最终 seed 区间 | 230–329（未用于调参、开发矩阵或前两次失效验证） |
| 环境 | Windows 11 x86_64；Python 3.12.13；JuPedSim 1.4.2 |

## 验收结果

最终矩阵覆盖 11 个场景、4 种规划方法、2 种资源协议及冻结 seed 规则，共 7216 个任务。

| 检查项 | 结果 |
|---|---:|
| 单元、集成与反例测试 | 29/29 PASS |
| 完成任务 | 7216/7216 |
| experiment error | 0 |
| 命中冻结 expectation | 7216/7216 |
| SUCCESS | 5342 |
| 保存轨迹离线复判一致 | 7216/7216 |
| 缺失 task hash | 0 |
| 净安全间距低于 `-1e-7` | 0 |

非成功终止为 1151 `PLAN_SEARCH_EXHAUSTED`、696 `INITIALIZATION_INVALID`、16 `CAPACITY_SHORTFALL`、8 `OFFSET_INVALID`、3 `PATH_UNREACHABLE`。这些结果是受验收的结构化终止，不是 runner 或程序异常；随机方法失败未被删除，也未通过放宽阈值改写。

按方法统计的 SUCCESS 率：Average CVT 1615/1804（89.52%）、DistMesh 968/1804（53.66%）、Equal Arc 1623/1804（89.97%）、Mass CVT 1136/1804（62.97%）。按协议统计：adaptive resource 2752/3608（76.27%），fixed N 2590/3608（71.78%）。这些比率是当前冻结场景集的经验结果，不是全局性能保证。

## G1–G12

| Gate | 状态 | 证据 |
|---|---|---|
| G1 | PASS | 严格配置；commit/source/config/input/task hash；固定 manifest 与复跑命令 |
| G2 | PASS | 人员圆盘包络、退化与 near-wall offset 夹具 |
| G3 | PASS | capacity、search exhaustion、matching 语义分离 |
| G4 | PASS | 四规划器、固定 N history、gap/分离检查 |
| G5 | PASS | visibility 绕障、整段合法性、可达匹配 |
| G6 | PASS | 结构化 `SafetyResult`、执行前区间复核、中心距离与净间隙 |
| G7 | PASS | 逐 guide 最大误差、速度与连续 hold 反例 |
| G8 | PASS | curve 与实际周期 gap 独立验收 |
| G9 | PASS | 平均剩余路径进展；路径重算→重分配→优先级让行；有界耗尽 |
| G10 | PASS | 早期失败同 schema 输出；程序异常单独记录 traceback |
| G11 | PASS | 7216/7216 最终矩阵完成、期望命中，且 7216/7216 离线复判一致 |
| G12 | PASS | `step1_theory.md` 的命题范围与实现限制对应 |

## 验证纪律与失效轮次

smoke（88 个任务）和 development-v2（2176 个任务）均为 0 experiment error，离线复判分别为 88/88 与 2176/2176 一致。开发期发现并修复初始化依赖异常未结构化的问题。

第一次 final（seeds 30–129）完成后，新增强制停滞反例发现 supervisor 使用总剩余路径进展与单 guide 容差比较，可能掩盖多 guide 停滞。该轮保留在 `results/closure-validation/` 但作废；代码改为 active guide 平均剩余路径进展，并新增实际触发完整三阶段恢复及耗尽的集成测试。

第二次 final（seeds 130–229）完成 7216/7216、0 experiment error，但 deterministic near-wall 夹具错误继承 validation 起始 seed，8 个任务未命中预设 `OFFSET_INVALID`。该轮保留在 `results/closure-validation-v2/` 但作废；runner 改为要求非随机场景显式固定 seed，并增加回归测试。

第三次 final 使用未查看的 seeds 230–329，在修复后的固定提交上运行，所有验收项通过。旧轮未覆盖，已查看的 seed 未复用。

## 复现命令与证据

```powershell
python -m pytest -q
python experiments/validation_runner.py --output results/closure-validation-v3 --phase validation --workers 16
python experiments/validation_runner.py --output results/closure-validation-v3 --reevaluate
python experiments/validation_runner.py --output results/closure-validation-v3 --plot-only
```

本地证据文件：

- `results/closure-validation-v3/summary.json`
- `results/closure-validation-v3/runs.csv`
- `results/closure-validation-v3/reevaluation_summary.json`
- `results/closure-validation-v3/validation_metrics.png`

提交内机器摘要为 `experiments/final_validation_summary.json`。原始结果目录受 `.gitignore` 管理，避免将大规模轨迹提交到仓库。

## 结论边界

CLOSED 仅适用于当前静态人群、全局快照、已知封闭场地、集中通信的 Step 1 范围。它不覆盖动态人群反馈、局部观测/未知地图探索、去中心化通信、真实机器人硬件安全、全局最优性或任意初态必达；这些属于后续 Step 2/3 或独立验证范围。
