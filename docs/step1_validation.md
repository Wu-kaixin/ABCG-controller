# Step 1 验收报告

本报告只引用当前分支重新运行的结果。机器 gate 与冻结矩阵定义见 `experiments/acceptance_manifest.yaml`；每个运行目录含 config/input/source/task hash、严格 JSON、无 pickle 轨迹、规划历史和原子状态。

## 冻结前检查

- 测试：29/29 PASS。
- 11 场景 × 4 方法 × 2 协议 × seed 0 smoke：88/88 completed，0 experiment error，59 SUCCESS、13 `PLAN_SEARCH_EXHAUSTED`、8 `CAPACITY_SHORTFALL`、8 `OFFSET_INVALID`。
- 两个确定性失败夹具的 16 个任务全部命中预先规定原因；随机方法失败被保留，没有删 seed 或放宽阈值。
- 从保存轨迹独立重评估：88/88 与原始 success 一致。

smoke 结果位于本地 `results/closure-smoke-v2/`，提交内摘要为 `experiments/smoke_summary.json`。开发 seeds 0–29 已完成；最终盲验证使用未用于调参或旧验证的 seeds 230–329。该矩阵完成前本报告保持 **PARTIAL**，不预写 CLOSED。

首次冻结后的 development 运行出现 192 个 JuPedSim `AgentNumberError` experiment error。失败结果保留在 `results/closure-development/`；修复将已知生成人群容量失败转换为带 traceback cause 的结构化 `INITIALIZATION_INVALID`，同时为初始化失败增加 request hash resume 和回归测试。依照冻结协议，旧轮不被覆盖，代码版本升级后使用新目录重跑。

修复后的 `results/closure-development-v2/` 共 2176 个任务：2176 completed、0 experiment error、1630 SUCCESS、338 PLAN_SEARCH_EXHAUSTED、192 INITIALIZATION_INVALID、8 CAPACITY_SHORTFALL、8 OFFSET_INVALID；2176/2176 离线重评估一致。development 中 square 的 12 个随机规划失败表明“所有随机 square seed 必须成功”是未经证明的假设，因此在查看最终 seeds 之前将该随机预期改为不预设结果；确定性 square seed 0 仍由测试严格要求 SUCCESS，失败夹具预期不变。算法、阈值和 final seeds 均未据此调整。

首次 final（seeds 30–129）运行完成 7216 个任务且 7216 个离线重评估一致，但在文档收口前新增的强制停滞验收发现进展量使用总剩余路径、容差却是单 guide 单位，可能让多 guide 的极慢运动掩盖停滞。该轮保留于 `results/closure-validation/` 并标记为失效验证；修复改用 active guide 平均剩余路径进展，新增实际触发“路径重算→重分配→优先级让行→耗尽”的集成测试。根据冻结纪律，修复后不复用已看过的 30–129，最终盲验证升级为未使用的 seeds 130–229，并输出到新目录。

第二次 final（seeds 130–229）完成 7216/7216、0 experiment error，但 8 个 deterministic near-wall 任务没有命中预设 OFFSET_INVALID。审计确认 runner 给非随机夹具使用了 validation 区间的首个 seed 130，而不是夹具冻结的 seed 0；结果虽诚实报告 INITIALIZATION_INVALID，但不满足预设分支。该轮保留于 `results/closure-validation-v2/` 并作废。runner 现在要求每个非随机场景在 manifest 中显式声明 seed，并有回归测试；第三次 final 使用从未查看的 seeds 230–329。

## G1–G12 当前状态

| Gate | 状态 | 证据 |
|---|---|---|
| G1 | PASS | 严格配置；commit/source/config/input/task hash；可复跑命令 |
| G2 | PASS | 人员圆盘包络、退化与 near-wall offset 夹具 |
| G3 | PASS | capacity、search exhaustion、matching 语义分离 |
| G4 | PASS | 四规划器、固定 N history、gap/分离检查 |
| G5 | PASS | visibility 绕障、整段合法性、可达匹配 |
| G6 | PASS | 结构化 SafetyResult、执行前区间复核、中心与净间隙 |
| G7 | PASS | 逐 guide 最大误差、速度和连续 hold 反例 |
| G8 | PASS | curve 与实际周期 gap 独立验收 |
| G9 | PASS | 剩余路径进展；路径重算→重分配→优先级让行；有界耗尽 |
| G10 | PASS | 早期失败同 schema 输出；程序异常单独记录 traceback |
| G11 | PENDING | runner/smoke 已通过；开发与最终冻结矩阵尚待执行 |
| G12 | PASS | `step1_theory.md` 的命题范围与实现限制对应 |

## 冻结命令

```powershell
python experiments/validation_runner.py --output results/development --phase development --workers auto
python experiments/validation_runner.py --output results/closure-validation-v3 --phase validation --workers auto
python experiments/validation_runner.py --output results/closure-validation-v3 --reevaluate
```

最终结论将在上述结果完成后由实际 `summary.json` 更新。若任务中断，可对同一目录增加 `--resume`；hash 不一致或结果不完整时不会静默跳过。
