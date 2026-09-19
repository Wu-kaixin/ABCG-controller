# Step 1 验收报告

本报告只引用本分支重新运行的证据，不沿用历史宣称。基线与新结果的命令、版本和输出摘要见 `docs/step1_status.md`；机器 gate 定义见 `experiments/acceptance_manifest.yaml`。

实际重新运行：原基线 11/11 tests；修改后 22/22 tests；square/rectangle × 四方法 seed 0 共 8 个 smoke，7 SUCCESS、1 `PLAN_SEARCH_EXHAUSTED`（rectangle/distmesh），失败未删除且未改阈值；另以 2 workers 跑 Equal Arc seeds 0、1，2/2 SUCCESS。逐运行摘要在 `experiments/smoke_summary.json`。最终 paired validation 仍为 0/8000 executed。

## G1–G12
| Gate | 状态 | 证据/原因 |
|---|---|---|
| G1 | PASS | 严格配置、commit/config/input hash、依赖版本 |
| G2 | PASS | 有效/退化/offset 测试 |
| G3 | PASS | capacity 与 search 状态分离 |
| G4 | PASS | 四规划器测试、CVT history |
| G5 | PASS | 绕障和不可达确定性夹具 |
| G6 | PASS | 中间碰撞、独立逐段重算 |
| G7 | PASS | 最大误差、速度、hold 反例 |
| G8 | PASS | far-from-curve 与 gap 反例 |
| G9 | FAIL | 仅有界停滞终止；未完成三阶段恢复 |
| G10 | PASS | 明确早期失败原因及结构化输出 |
| G11 | FAIL | 8 个 smoke 中 7 PASS/1 FAIL；8000 个冻结 paired tasks（100 seeds×10随机场景×4方法×2协议）0 executed；协议 runner 尚不完整 |
| G12 | PASS | `step1_theory.md` 与实现边界对应 |

因此 Step 1 为 **PARTIAL**，不是 CLOSED。核心 smoke 只证明所列输入上的工程行为；最终矩阵未执行，不能报告成功率。续跑前须先完成固定-N/adaptive manifest runner、hash resume、恢复 supervisor；随后使用未用于调参的 30–129 seeds。

建议续跑入口（当前已有单配置 seed batch）：
`python run.py --config configs/step1/square.yaml --output results/validation-square --seeds $(seq 30 129) --workers auto --no-plots`

PowerShell：
`python run.py --config configs/step1/square.yaml --output results/validation-square --seeds (30..129) --workers auto --no-plots`
