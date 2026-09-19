# Step 1 状态与需求映射

基线 commit 为 `9697359`；闭环工作分支为 `codex/step1-closure`。当前验证环境是 Windows 11 x86_64、Python 3.12.13、JuPedSim 1.4.2。原始基线 11 项测试通过，但只使用 controller 收敛/RMSE 判据；闭环实现改为从已执行轨迹独立重算全部 criteria。

## WP 检查点

- WP0：完成仓库、依赖、边界、CVT、assignment、safety 与 runner 审计；保留原工作树并建立独立分支。
- WP1：严格配置校验；初始化/规划/执行早期失败均生成同 schema 结果；独立 evaluator 重算 geometry/resource/plan/path/safety/arrival/curve/gap/coverage；记录 commit、source、config、input 和 task hash。
- WP2：观测人体圆盘凸包、保守部署曲线、$H-2\epsilon_s$ 预算、固定 N 与自适应搜索、四种方法和逐候选 history 已实现。人体半径不会在导航障碍中重复膨胀。
- WP3：visibility graph + Dijkstra、路径代价匹配、结构化 `SafetyResult`、执行前区间复核、中心距离与净间隙均已记录。停滞依据剩余路径检测；恢复顺序为路径重算→可达重分配→确定性优先级让行，且受 `max_replans` 有界约束。
- WP4：11 类场景、机器 manifest、固定-N/自适应协议、进程并行、原子状态、hash resume、离线重评估、CSV/JSON 汇总和绘图入口已实现。

## 当前证据检查点

- 单元/集成/反例测试：26/26 PASS。
- manifest smoke：88/88 completed，0 experiment error，88/88 expected status 命中；59 SUCCESS、13 PLAN_SEARCH_EXHAUSTED、8 CAPACITY_SHORTFALL、8 OFFSET_INVALID。
- smoke 离线重评估：88/88 与原始 success 判定一致。
- smoke 证据目录：`results/closure-smoke-v2/`（gitignore 下的本地结果）；可提交摘要为 `experiments/smoke_summary.json`。
- 开发矩阵与最终 seeds 30–129 矩阵的结论记录在 `docs/step1_validation.md`；在最终矩阵完成前状态仍为 PARTIAL。

## Schema 与限制

结果 schema 为 `1.1.0`。`success` 仅表示冻结 Step 1 范围内的独立验收，不表示动态人群遏制、局部未知环境探索、真实机器人安全、全局最优或从任意初态必然到达。`demand` 只是规划权重，不是已验证的行为风险模型。
