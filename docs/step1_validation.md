# Step 1 验收报告

本报告只引用当前分支重新运行的结果。机器 gate 与冻结矩阵定义见 `experiments/acceptance_manifest.yaml`；每个运行目录含 config/input/source/task hash、严格 JSON、无 pickle 轨迹、规划历史和原子状态。

## 冻结前检查

- 测试：27/27 PASS。
- 11 场景 × 4 方法 × 2 协议 × seed 0 smoke：88/88 completed，0 experiment error，59 SUCCESS、13 `PLAN_SEARCH_EXHAUSTED`、8 `CAPACITY_SHORTFALL`、8 `OFFSET_INVALID`。
- 两个确定性失败夹具的 16 个任务全部命中预先规定原因；随机方法失败被保留，没有删 seed 或放宽阈值。
- 从保存轨迹独立重评估：88/88 与原始 success 一致。

smoke 结果位于本地 `results/closure-smoke-v2/`，提交内摘要为 `experiments/smoke_summary.json`。开发 seeds 0–29 和最终未用于调参的 seeds 30–129 矩阵将在代码冻结后运行；运行前本报告保持 **PARTIAL**，不预写 CLOSED。

首次冻结后的 development 运行出现 192 个 JuPedSim `AgentNumberError` experiment error。失败结果保留在 `results/closure-development/`；修复将已知生成人群容量失败转换为带 traceback cause 的结构化 `INITIALIZATION_INVALID`，同时为初始化失败增加 request hash resume 和回归测试。依照冻结协议，旧轮不被覆盖，代码版本升级后使用新目录重跑。

修复后的 `results/closure-development-v2/` 共 2176 个任务：2176 completed、0 experiment error、1630 SUCCESS、338 PLAN_SEARCH_EXHAUSTED、192 INITIALIZATION_INVALID、8 CAPACITY_SHORTFALL、8 OFFSET_INVALID；2176/2176 离线重评估一致。development 中 square 的 12 个随机规划失败表明“所有随机 square seed 必须成功”是未经证明的假设，因此在查看最终 seeds 之前将该随机预期改为不预设结果；确定性 square seed 0 仍由测试严格要求 SUCCESS，失败夹具预期不变。算法、阈值和 final seeds 均未据此调整。

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
python experiments/validation_runner.py --output results/validation --phase validation --workers auto
python experiments/validation_runner.py --output results/validation --reevaluate
```

最终结论将在上述结果完成后由实际 `summary.json` 更新。若任务中断，可对同一目录增加 `--resume`；hash 不一致或结果不完整时不会静默跳过。
