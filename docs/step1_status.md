# Step 1 状态与需求映射

基线 commit 为 `9697359`；闭环工作分支为 `codex/step1-closure`。当前验证环境是 Windows 11 x86_64、Python 3.12.13、JuPedSim 1.4.2。原始基线 11 项测试通过，但只使用 controller 收敛/RMSE 判据；闭环实现改为从已执行轨迹独立重算全部 criteria。

## WP 检查点

- WP0：完成仓库、依赖、边界、CVT、assignment、safety 与 runner 审计；保留原工作树并建立独立分支。
- WP1：严格配置校验；初始化/规划/执行早期失败均生成同 schema 结果；独立 evaluator 重算 geometry/resource/plan/path/safety/arrival/curve/gap/coverage；记录 commit、source、config、input 和 task hash。
- WP2：观测人体圆盘凸包、保守部署曲线、$H-2\epsilon_s$ 预算、固定 N 与自适应搜索、四种方法和逐候选 history 已实现。人体半径不会在导航障碍中重复膨胀。
- WP3：visibility graph + Dijkstra、路径代价匹配、结构化 `SafetyResult`、执行前区间复核、中心距离与净间隙均已记录。停滞依据剩余路径检测；恢复顺序为路径重算→可达重分配→确定性优先级让行，且受 `max_replans` 有界约束。
- WP4：11 类场景、机器 manifest、固定-N/自适应协议、进程并行、原子状态、hash resume、离线重评估、CSV/JSON 汇总和绘图入口已实现。

## 当前证据检查点

- 单元/集成/反例测试：29/29 PASS。
- manifest smoke：88/88 completed，0 experiment error，88/88 expected status 命中；59 SUCCESS、13 PLAN_SEARCH_EXHAUSTED、8 CAPACITY_SHORTFALL、8 OFFSET_INVALID。
- smoke 离线重评估：88/88 与原始 success 判定一致。
- 首次 development 矩阵保留在 `results/closure-development/`：2176 中 192 个 JuPedSim `AgentNumberError` 被 runner 正确记为 EXPERIMENT_ERROR，暴露初始化依赖异常未结构化的问题；修复后该异常统一为 `INITIALIZATION_INVALID`，并增加回归测试。该失败轮不作为最终证据。
- 修复后的 development-v2：2176/2176 completed、0 experiment error；1630 SUCCESS、338 PLAN_SEARCH_EXHAUSTED、192 INITIALIZATION_INVALID、8 CAPACITY_SHORTFALL、8 OFFSET_INVALID；2176/2176 离线重评估一致。随机 square 的 12 个真实规划失败说明不能预设所有随机 seed 成功，因此在最终验证前删除该过强预期，未改算法参数或阈值。
- 首次 final 矩阵虽 7216/7216 完成且重评估一致，但随后新增的强制停滞反例发现 supervisor 将所有 guide 的路径进展总和与单 guide 容差比较，可能掩盖停滞。该轮保留在 `results/closure-validation/` 但作废；实现改为 active guide 平均剩余路径进展，并把完整三阶段恢复及耗尽加入测试，升级后重跑。
- 第二次 final（seeds 130–229）7216/7216 完成、0 experiment error，但 deterministic near-wall 夹具错误继承 validation 起始 seed 130，导致 8 个预设 OFFSET_INVALID 未命中。结果保留在 `results/closure-validation-v2/` 但作废；runner 改为要求非随机场景显式固定 seed，并增加 manifest 回归测试。第三次 final 使用未看过的 230–329。
- smoke 证据目录：`results/closure-smoke-v2/`（gitignore 下的本地结果）；可提交摘要为 `experiments/smoke_summary.json`。
- 开发矩阵与最终未使用 seeds 230–329 矩阵的结论记录在 `docs/step1_validation.md`；在第三次最终矩阵完成前状态仍为 PARTIAL。

## Schema 与限制

结果 schema 为 `1.1.0`。`success` 仅表示冻结 Step 1 范围内的独立验收，不表示动态人群遏制、局部未知环境探索、真实机器人安全、全局最优或从任意初态必然到达。`demand` 只是规划权重，不是已验证的行为风险模型。
