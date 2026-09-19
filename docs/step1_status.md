# Step 1 状态与需求映射

**状态：CLOSED（冻结的 Step 1 范围）**

基线 commit 为 `9697359`；闭环工作分支为 `codex/step1-closure`。最终盲验证锁定代码 commit `c9d751684f3981c4539efdf430fd9f4cbf953e19`，环境为 Windows 11 x86_64、Python 3.12.13、JuPedSim 1.4.2。原始基线只使用 controller 收敛/RMSE 判据；闭环实现改为从已执行轨迹独立重算全部验收条件。

## WP 检查点

- WP0：完成仓库、依赖、边界、CVT、assignment、safety 与 runner 审计；保留原工作树并建立独立分支。
- WP1：严格配置校验；初始化、规划和执行早期失败均生成同 schema 结果；独立 evaluator 重算 geometry/resource/plan/path/safety/arrival/curve/gap/coverage；记录 commit、source、config、input 和 task hash。
- WP2：观测人体圆盘凸包、保守部署曲线、$H-2\epsilon_s$ 预算、固定 N 与自适应搜索、四种方法和逐候选 history 已实现。人体半径不会在导航障碍中重复膨胀。
- WP3：visibility graph + Dijkstra、路径代价匹配、结构化 `SafetyResult`、执行前区间复核、中心距离与净间隙均已记录。停滞依据 active guide 的平均剩余路径进展检测；恢复顺序为路径重算→可达重分配→确定性优先级让行，且受 `max_replans` 有界约束。
- WP4：11 类场景、机器 manifest、固定-N/自适应协议、进程并行、原子状态、hash resume、离线重评估、CSV/JSON 汇总和绘图入口已实现。

## 最终证据

- 单元、集成与反例测试：29/29 PASS。
- smoke：88/88 completed，0 experiment error，88/88 expected status 命中；88/88 离线重评估一致。
- development-v2：2176/2176 completed，0 experiment error；2176/2176 离线重评估一致。
- 最终盲验证 v3（seeds 230–329）：7216/7216 completed，0 experiment error，7216/7216 expectation 命中。
- 最终终止分布：5342 SUCCESS、1151 PLAN_SEARCH_EXHAUSTED、696 INITIALIZATION_INVALID、16 CAPACITY_SHORTFALL、8 OFFSET_INVALID、3 PATH_UNREACHABLE。失败被保留并按冻结语义验收，不等同于实验执行错误。
- 保存轨迹离线复判：7216/7216 与在线判定一致。
- 数据审计：0 个缺失 task hash、0 个低于 `-1e-7` 的净安全间距；全部结果的 commit/source 均一致，`dirty=false`。
- manifest SHA-256：`b87a4735aad4aff4040e069c6db64020d2c7ba641351000599b895bd823c3eef`；source SHA-256：`945f842557b277ae6e516eec528282d0a1fe4be4f586d8eafa0da3bf6195a408`。

完整说明见 `docs/step1_validation.md`，机器可读摘要见 `experiments/final_validation_summary.json`。本地原始证据位于 `results/closure-validation-v3/`。

## 失效轮次的处理

- `results/closure-development/` 暴露 JuPedSim `AgentNumberError` 未结构化；修复后统一为 `INITIALIZATION_INVALID`，旧结果保留但不作为最终证据。
- `results/closure-validation/` 随后被强制停滞反例推翻；修复为平均剩余路径进展并新增完整恢复/耗尽测试，旧轮作废。
- `results/closure-validation-v2/` 暴露 deterministic fixture 错误继承 validation seed；runner 改为要求非随机场景显式固定 seed 并增加回归测试，旧轮作废。
- 每次修复后均换用未查看的 seed 区间和新输出目录，没有覆盖失败证据或回用已查看的最终 seeds。

## Schema 与限制

结果 schema 为 `1.1.0`。这里的 CLOSED 只表示冻结 Step 1 命题已实现并通过既定 gates；不表示动态人群遏制、局部未知环境探索、真实机器人安全、全局最优或从任意初态必然到达。`demand` 只是规划权重，不是已验证的行为风险模型。
