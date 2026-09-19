# ABCG-controller

**Adaptive Guide-Agent Deployment for Unknown Dynamic Crowds**

当前实现并严格评价 Step 1：在封闭场地中，围绕一个静态、未知轮廓的人群部署外部引导代理。人群不受引导代理影响；观测为全局快照，通信不受限。验收结论只以 `docs/step1_validation.md` 中冻结矩阵的实际结果为准。

## 项目结构

| 位置 | 职责 |
|---|---|
| `configs/step1/square.yaml` | 封闭正方形场景（20 × 20 m） |
| `configs/step1/rectangle.yaml` | 封闭长方形场景（28 × 16 m） |
| `configs/step2/`、`configs/step3/` | 预留场景目录 |
| `environment.py` | JuPedSim 人群初始化、个体属性、观测接口 |
| `scene.py` | 场地构建与场景扩展入口 |
| `controller/abcg.py` | 部署准备、代理分配与速度反馈 |
| `controller/boundary.py` | 从观测估计人群边界，构造部署曲线 |
| `controller/coverage.py` | Equal Arc、Average/Mass CVT、DistMesh-inspired 周期规划 |
| `controller/navigation.py` | 静态 visibility graph、Dijkstra 和可达匹配 |
| `controller/safety.py` | 速度安全过滤与运动路径检查 |
| `evaluator.py` | 不依赖 controller settled 标志的轨迹验收 |
| `interfaces.py` | 观测数据和未来局部控制接口 |
| `run.py` | 读取配置、运行仿真、保存结果 |
| `experiments/validation_runner.py` | manifest 驱动的固定-N/自适应批量验证、resume、重评估和汇总 |
| `visualization.py` | 绘制场景和代理轨迹 |
| `tests/test_step1.py` | 必要的功能与安全测试 |
| `results/` | 本地实验输出 |

## 运行

使用 Python 3.12，在独立环境安装依赖：

```bash
python -m pip install -e ".[dev]"
python run.py --config configs/step1/square.yaml --output results/square
python run.py --config configs/step1/rectangle.yaml --output results/rectangle
python -m pytest -q
```

每次使用空的结果目录，或显式传入 `--resume`。输出包括严格 JSON 指标、无 pickle 的轨迹数组、逐候选规划历史、原子任务状态和可选图片。resume 仅在 commit/source/config/input/method/protocol hash 均匹配且结果文件完整时跳过。

多个随机种子可以并行运行：

```bash
python run.py --config configs/step1/square.yaml --output results/batch --seeds 0 1 2 3 4 --workers auto --no-plots
```

PowerShell 单行：

```powershell
python run.py --config configs/step1/square.yaml --output results/batch --seeds (0..4) --workers auto --no-plots
```

固定 N、公平对照和 resume：

```powershell
python run.py --config configs/step1/square.yaml --output results/fixed --protocol fixed_n --fixed-n 24 --method equal_arc --no-plots
python run.py --config configs/step1/square.yaml --output results/fixed --protocol fixed_n --fixed-n 24 --method equal_arc --no-plots --resume
python run.py --reevaluate results/fixed
```

manifest smoke、开发矩阵和最终冻结矩阵：

```powershell
python experiments/validation_runner.py --output results/smoke --phase development --smoke --workers auto
python experiments/validation_runner.py --output results/development --phase development --workers auto
python experiments/validation_runner.py --output results/validation --phase validation --workers auto
python experiments/validation_runner.py --output results/validation --reevaluate
python experiments/validation_runner.py --output results/validation --plot-only
```

`--workers auto` 使用可用 CPU 数与任务数的较小值；worker 内限制数值库线程。完整冻结矩阵见 `experiments/acceptance_manifest.yaml`。

## 当前模型

1. JuPedSim 生成人群位置后保持固定；引导代理通过速度输入逐步移动。
2. 房间边界已知；人群生成区域仅环境使用，控制器只能获得观测点和个体属性。
3. 最小边界模型采用观测点的**凸包**，再向外偏移生成部署曲线。它对凹形人群采用保守包络，不恢复凹陷细节。
4. `budget_gap` 仅给出起点建议；规划使用 `max_gap_limit-2*arc_tolerance` 的必要下界，在全部可用数量内作有界搜索。搜索耗尽不冒充数学不可行。
5. 人体半径影响初始化间距和安全距离；`demand` 权重影响部署分布。两种属性均可在配置中调整，设 `std: 0` 可进行同质性对照。
6. 分配使用静态可见图路径长度；速度经过安全过滤并在执行前检查整个采样区间。人体圆盘已进入占据包络，导航只再膨胀 guide 半径与 clearance，避免重复计算人体半径。
7. 停滞使用剩余 waypoint 路径长度而非目标欧氏距离检测；恢复顺序固定为路径重算、可达重分配、确定性优先级让行，预算耗尽后终止。

`success` 只有在 geometry/resource/plan/path/safety/arrival/curve/gap/coverage 全部独立通过且终端条件连续保持时成立，尚不表示动态人群遏制、真实机器人安全、未知环境搜索或全局最优。

## 从哪里开始修改

- **改场景和参数**：修改两个 YAML 文件。
- **改人群边界模型**：替换 `controller/boundary.py` 中的估计函数。
- **改部署策略或控制律**：修改 `controller/coverage.py` 或 `controller/abcg.py`。
- **加入新场景**：扩展 `scene.py` 的 `SCENES`。非矩形场地还需相应的墙壁安全约束。
- **Step 2 动态人群**：扩展 `Environment.advance()`，接入 JuPedSim 动力学及引导交互。
- **Step 3 去中心化**：实现 `interfaces.py` 中的 `LocalPolicy`，加入局部观测和邻居通信。

当前只实现 Step 1，Step 2、Step 3 为扩展入口。
