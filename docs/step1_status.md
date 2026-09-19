# Step 1 状态与需求映射

基线：`9697359`，分支 `feat/step1-closure`；Python 3.12.13，Linux x86_64。原始 11 tests PASS；原 square/rectangle 在旧 RMSE 判据下均报 CONVERGED，但没有独立逐-guide/curve/gap/hold 验收。

## WP 检查点
- WP0：完成仓库、依赖、边界/CVT/assignment/safety/runner 审计。
- WP1：严格新 schema；独立 evaluator；criteria、三类状态、provenance 和结构化早期失败。
- WP2：含半径的保守外包、$H-2\epsilon_s$ 搜索、四方法、每候选诊断。
- WP3：visibility graph + Dijkstra、路径代价匹配、结构化 SafetyResult、执行前区间复核。停滞有界终止已实现；路径重算/重分配/优先级让行的完整恢复序列未实现。
- WP4：11 类场景配置、理论、机器 manifest 与 8-run smoke 证据已交付；smoke 为 7 PASS/1 PLAN_SEARCH_EXHAUSTED。冻结的 seeds 30–129 四方法×双协议矩阵未执行，固定-N batch 协议/原子 resume/汇总绘图也未完整实现。

## Schema 与状态
配置含 method、budget/max gap、position/speed/curve/arc tolerance、物理 clearance 与独立 numeric tolerance。结果 `schema_version=1.0.0`。终止状态集中于 `run.STATUSES`；程序异常不吞并。计算预算在 manifest 冻结：开发 0–29、最终 30–129。

## 结论
当前为 **PARTIAL**。核心正向闭环和关键否定语义有代码与测试，但 G9、G11 未达到任务书 CLOSED 门槛。不得将此状态解释成任意未知人群、任意初态可达，也不得将 demand 当作行为模型。
