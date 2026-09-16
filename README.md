# ABCG-controller

**Adaptive Guide-Agent Deployment for Unknown Dynamic Crowds**

一个便于逐步修改的 Step 1 研究起点：JuPedSim 生成人群快照，ABCG 根据观测估计边界、规划部署位置并控制外部引导代理。当前只研究封闭正方形和长方形场地中的单一静态人群。

## 快速运行

使用 **Python 3.12**。建议在独立环境安装：

```bash
python -m venv .venv
```

Windows PowerShell 激活：`.\.venv\Scripts\Activate.ps1`；Linux/macOS 激活：`source .venv/bin/activate`。

```bash
python -m pip install -e ".[dev]"
python run.py --config configs/step1/square.yaml --output results/square
python run.py --config configs/step1/rectangle.yaml --output results/rectangle
python -m pytest -q
```

结果目录必须为空，避免覆盖以前的实验。JuPedSim 固定为本轮验证使用的 `1.4.2`；它自带的可视化依赖可能使安装包较大。本项目出图使用 Matplotlib，不需要打开 GUI。

多种子实验自动使用多进程，每个进程运行一个独立实验：

```bash
python run.py --config configs/step1/square.yaml --output results/square_batch --seeds 0 1 2 3 4 5 6 7 8 9 --workers auto --no-plots
```

`--workers auto` 根据可用 CPU 数和实验数选择进程数，并限制进程内数值库线程数。一个实验的时间步按顺序执行。`--workers 4` 可以手动设置进程数。

## 只需要了解的几个位置

| 位置 | 用途 |
|---|---|
| `configs/step1/square.yaml`、`rectangle.yaml` | 两个固定封闭场地及全部实验参数 |
| `configs/step2/`、`configs/step3/` | 预留目录，尚无实验实现 |
| `controller/abcg.py` | 速度反馈、状态机与执行接口 |
| `controller/boundary.py` | 人群边界估计、部署曲线构造 |
| `controller/coverage.py` | 均匀或需求加权的周期弧长覆盖规划 |
| `controller/safety.py` | 速度安全过滤 |
| `controller/assignment.py`、`resources.py` | 目标分配与引导代理数量选择 |
| `controller/arclength.py`、`radial.py`、`common.py` | 已移植的底层几何工具 |
| `environment.py` | JuPedSim 初始化、固定人群、观测接口与异质性 |
| `scene.py`、`interfaces.py` | 场地和未来局部感知/通信接口 |
| `run.py`、`visualization.py` | 实验入口、结果记录与出图 |
| `tests/` | 源算法回归测试及新框架集成测试 |

不用把所有文件读完才开始。先修改 YAML，再看 `environment.py` 和 `controller/abcg.py`。

## 当前模型与算法

- 正方形场地为 **20 × 20 m**，长方形为 **28 × 16 m**，四周封闭，无开口。人群生成区域位于房间内部。
- 场地边界、人群估计边界、部署曲线是三个不同对象。`crowd.spawn_vertices` 仅供环境生成人群，控制器不会接收这份生成几何。
- Step 1 假设全局观测和无限通信；“未知”表示人群轮廓不预先给定，尚未实现搜索/遮挡/局部感知。
- JuPedSim `distribute_by_number` 生成有间距的人群点集，之后严格固定。因此这是 **JuPedSim 静态快照上的部署测试**，当前没有调用 `Simulation.iterate()` 推进行人动力学。
- 初始引导代理沿场地内侧排列，与最终目标独立。代理多于所需数量时明确记录备用代理。
- 执行流程：观测 → alpha/radial 边界估计 → 多边形外扩部署曲线 → 代理数量选择 → 弧长覆盖规划 → 匈牙利分配 → 速度反馈和安全过滤。
- 部署曲线使用它自身的弧长。数量策略 `ceil(L / g_req)` 是平均间距预算；加权规划后的最大间隙另行记录，不能把该预算当成最大间隙保证。
- 引导代理按 `q[k+1] = q[k] + dt * u[k]` 更新，应用的速度与轨迹都会保存。没有通过强行裁剪位置来隐藏碰撞。
- 源仓库严格的法向偏移构造仍保留供测试；新入口明确使用 `polygon_buffer` 部署策略。非法几何、越墙、离观测人群太近、资源不足和超时都会显式报告。

### 适度异质性

| 属性 | Step 1 中的作用 |
|---|---|
| `radius` | 影响初始化间距；最大人体半径参与保守安全距离 |
| `demand_weight` | 通过空间插值形成部署需求密度，改变加权覆盖目标 |
| `desired_speed`、`time_gap` | 保留给未来 JuPedSim 动态模型；当前不产生运动 |

默认需求权重只在 `[0.75, 1.25]` 内变化，是研究用的合成属性，尚未标定为真实人群风险。当前假定这些属性可观测。

将 `controller.deployment.weighted` 改为 `false` 可运行移植的均匀弧长 CVT；将 `crowd.heterogeneity.enabled` 改为 `false` 则所有属性采用其均值。需求密度与边界估计置信度各自独立，后者只影响 Lloyd 更新增益。

安全间距采用中心距：

- 引导代理—人群：引导代理半径 + 最大人体半径 + `crowd_clearance`；
- 引导代理—引导代理：两倍引导代理半径 + `guide_clearance`；
- 引导代理—墙壁：引导代理半径 + `wall_clearance`。

## 输出与结果解释

每次运行保存：

- `metrics.json`：有效性、收敛状态、跟踪误差、最终最大弧长间隙和安全距离；
- `trajectory.npz`：固定人群、个体属性、引导轨迹、名义/实际速度和目标点；
- `boundary.json`、`deployment.json`、`plan.json`、`assignment.json`、`resources.json`：各阶段诊断，未执行的阶段不生成；
- `trace.json`：逐步状态、安全过滤状态及残差；
- `resolved_config.json`、`manifest.json`：配置、随机种子、依赖版本、代码哈希；
- `deployment.png`：场地、人群边界、部署曲线与引导轨迹。

`deployment_success` 仅表示：引导代理收敛到计划目标、固定人群未移动、执行路径满足所设安全距离。它**不表示动态遏制、现实人群安全或全局最优**。安全检查包含相邻仿真时刻之间的直线运动段，不只是离散端点。

程序正常结束不等于研究成功。`CAPACITY_SHORTFALL`、`BOUNDARY_INVALID`、`OFFSET_INVALID`、`TIMEOUT` 等科学失败仍然写入结果，批量统计保留这些样本。配置或环境生成错误会抛出异常。

## 后续扩展入口

- **添加场景**：从 `scene.py` 的 `Scenario` 接口开始。非矩形墙壁/障碍物还需要相应的安全约束实现，当前不会假装支持。
- **Step 2**：在 `environment.py` 扩展 `advance()`，接入人群动力学及明确的 guide–crowd 作用模型，再处理多群体移动、分裂和合并。
- **Step 3**：沿用 `interfaces.py` 的局部观测、邻居消息、群体假设、资源提议接口。当前控制器仍为集中式；保留接口不等于已经实现去中心化。

移植来源、范围和验证结果见 [docs/MIGRATION.md](docs/MIGRATION.md)。所有旧论文、证明、历史结果仍保留在源仓库；本项目不继承其通过声明。
