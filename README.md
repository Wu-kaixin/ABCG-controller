# ABCG Controller

**Auditable guide-agent deployment for crowd containment research**

[![Step 1](https://img.shields.io/badge/Step%201-CLOSED-2ea44f)](docs/step1_validation.md)
[![CI](https://github.com/Wu-kaixin/ABCG-controller/actions/workflows/ci.yml/badge.svg)](https://github.com/Wu-kaixin/ABCG-controller/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

ABCG Controller 研究如何在未知人群轮廓外部署引导代理（guide agents），形成安全、可复现、可独立验收的周期覆盖。项目当前已完成 **Step 1：单个静态人群、无 guide–crowd 动力学交互、无通信限制**；Step 2 将在此基线上加入动态人群及引导交互。

> [!IMPORTANT]
> Step 1 已在冻结范围内标记为 **CLOSED**。最终矩阵 7216/7216 完成、0 个实验执行错误、7216/7216 命中冻结预期，保存轨迹离线复判 7216/7216 一致。完整证据见[验收报告](docs/step1_validation.md)和[机器摘要](experiments/final_validation_summary.json)。

## 核心能力

- 从带半径的人群观测构建保守占据包络与部署曲线。
- 提供 Equal Arc、Average CVT、Mass CVT、DistMesh-inspired 四种周期部署方法。
- 支持自适应资源搜索与固定 guide 数量两种公平对照协议。
- 使用 visibility graph、Dijkstra 和路径代价匹配进行静态绕障分配。
- 对 guide–guide、guide–human、guide–wall 执行连续采样区间安全复核。
- 通过剩余路径进展识别停滞，并执行有界的重算、重分配和优先级让行。
- 从保存轨迹独立重算全部验收条件，不依赖 controller 的内部“成功”标志。
- 记录 commit、源码、配置、输入和任务哈希，支持安全 resume 与批量复现。

## 系统流程

```mermaid
flowchart LR
    C["YAML 场景与实验配置"] --> E["Environment<br/>静态人群与 guide 初始化"]
    E --> O["全局 Observation<br/>位置、半径、demand"]
    O --> B["Boundary<br/>人体圆盘凸包与部署曲线"]
    B --> P["Coverage Planner<br/>四种分布方法"]
    P --> N["Navigation<br/>可见图、最短路、匹配"]
    N --> A["ABCG Controller<br/>跟踪与有限停滞恢复"]
    A --> S["Safety Filter<br/>速度约束与区间复核"]
    S --> T["Trajectory<br/>无 pickle 的 NPZ 轨迹"]
    T --> V["Independent Evaluator<br/>九类 criteria 重算"]
    V --> R["JSON、CSV、状态、图表"]
    S -->|"guide 状态反馈"| A
```

## 当前研究范围

| 阶段 | 人群 | guide–crowd 交互 | 观测与通信 | 状态 |
|---|---|---|---|---|
| Step 1 | 单个静态人群 | 无 | 全局快照、集中控制、通信不受限 | **CLOSED** |
| Step 2 | 动态人群 | 有 | 暂保留全局观测与通信 | 下一阶段 |
| Step 3 | 动态人群 | 有 | 局部观测、邻居通信、去中心化策略 | 预留接口 |

Step 1 的 CLOSED 不代表真实机器人安全、动态人群遏制、全局最优或任意初态必达。精确定义和理论边界见[模型与命题说明](docs/step1_theory.md)。

## 最终验收快照

| 指标 | 结果 |
|---|---:|
| 单元、集成与反例测试 | 29/29 PASS |
| 最终冻结任务 | 7216 |
| 完成任务 | 7216/7216 |
| 实验执行错误 | 0 |
| 命中冻结终止语义 | 7216/7216 |
| `SUCCESS` | 5342 |
| 离线独立复判一致 | 7216/7216 |
| 缺失 task hash | 0 |
| 净安全间距低于 `-1e-7` | 0 |

非成功任务以 `PLAN_SEARCH_EXHAUSTED`、`INITIALIZATION_INVALID`、`CAPACITY_SHORTFALL`、`OFFSET_INVALID` 或 `PATH_UNREACHABLE` 结构化终止。它们保留了随机方法的真实失败和确定性反例，不属于 runner 异常，也没有通过删 seed 或放宽阈值隐藏。

## 快速开始

### 1. 安装

需要 Python 3.12 或更高版本。建议使用独立虚拟环境：

```bash
git clone https://github.com/Wu-kaixin/ABCG-controller.git
cd ABCG-controller
python -m venv .venv
```

激活环境并安装：

```bash
# Linux / macOS
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 2. 运行一个场景

```bash
python run.py \
  --config configs/step1/square.yaml \
  --output results/quickstart \
  --method equal_arc \
  --protocol adaptive_resource
```

PowerShell：

```powershell
python run.py `
  --config configs/step1/square.yaml `
  --output results/quickstart `
  --method equal_arc `
  --protocol adaptive_resource
```

每个运行目录通常包含：

```text
results/quickstart/
├── config.yaml       # 完整输入快照
├── metrics.json      # 独立验收指标与复现元数据
├── planning.json     # 逐候选规划历史
├── state.json        # 原子任务状态
├── trajectory.npz    # 无 pickle 轨迹
└── scene.png         # 可选可视化
```

### 3. 复判与重新绘图

```bash
python run.py --reevaluate results/quickstart
python visualization.py --result results/quickstart
```

离线复判只读取落盘输入和轨迹，重新计算 geometry、resource、plan、path、safety、arrival、curve、gap、coverage，不复用 controller 的内部判定。

## 方法与实验协议

### 部署方法

| 方法 | CLI 值 | 目标 |
|---|---|---|
| Equal Arc | `equal_arc` | 沿部署曲线等弧长分布 |
| Average CVT | `average_cvt` | 基于几何密度的周期 CVT |
| Mass CVT | `mass_cvt` | 根据 demand 权重调整覆盖密度 |
| DistMesh-inspired | `distmesh` | 通过相邻间距均衡迭代分布 |

### 资源协议

| 协议 | CLI | 语义 |
|---|---|---|
| Adaptive Resource | `--protocol adaptive_resource` | 在资源上限内有界搜索可接受 guide 数量 |
| Fixed N | `--protocol fixed_n --fixed-n 24` | 固定 guide 数量，用于公平方法对照 |

固定 N 示例：

```bash
python run.py \
  --config configs/step1/square.yaml \
  --output results/fixed-24 \
  --method mass_cvt \
  --protocol fixed_n \
  --fixed-n 24
```

## 批量实验与可恢复执行

多 seed 并行运行：

```bash
python run.py \
  --config configs/step1/square.yaml \
  --output results/seed-batch \
  --seeds 0 1 2 3 4 \
  --workers auto \
  --no-plots
```

任务中断后可使用相同命令并追加 `--resume`。只有 commit/source/config/input/method/protocol/task hash 全部匹配且结果文件完整的任务才会跳过；不匹配的旧结果不会被静默复用。

## 验证工作流

快速测试：

```bash
python -m pytest -q
```

manifest smoke：

```bash
python experiments/validation_runner.py \
  --output results/smoke \
  --phase development \
  --smoke \
  --workers auto
```

完整开发矩阵与最终冻结矩阵计算量较大：

```bash
python experiments/validation_runner.py --output results/development --phase development --workers auto
python experiments/validation_runner.py --output results/validation --phase validation --workers auto
python experiments/validation_runner.py --output results/validation --reevaluate
python experiments/validation_runner.py --output results/validation --plot-only
```

冻结的场景、seed、方法、协议和 gate 定义在 [`experiments/acceptance_manifest.yaml`](experiments/acceptance_manifest.yaml)。CI 在 Ubuntu 与 Windows 上运行测试。

## 项目结构

```text
ABCG-controller/
├── configs/step1/                  # 基准场景与验收夹具
├── controller/
│   ├── abcg.py                     # 总体规划、反馈与停滞恢复
│   ├── boundary.py                 # 人群包络与部署曲线
│   ├── coverage.py                 # 四种周期部署方法
│   ├── navigation.py               # 可见图、Dijkstra、可达匹配
│   └── safety.py                   # 安全速度与连续区间复核
├── docs/
│   ├── step1_status.md             # 需求与实现映射
│   ├── step1_theory.md             # 数学语义和结论边界
│   └── step1_validation.md         # 最终验收报告
├── experiments/
│   ├── acceptance_manifest.yaml    # 冻结验证协议
│   ├── final_validation_summary.json
│   └── validation_runner.py        # 并行、resume、汇总与复判
├── tests/                          # 单元、集成和反例测试
├── environment.py                 # JuPedSim 初始化与观测
├── evaluator.py                   # 独立轨迹验收
├── interfaces.py                  # 全局观测与未来局部策略接口
├── run.py                         # 单次/批量实验入口
└── visualization.py               # 保存结果可视化
```

## Step 2 开发起点

Step 2 应从 `develop` 分支开始，并保留全部 Step 1 测试作为回归门槛。推荐的最小演进顺序：

1. 在 `Environment.advance()` 中接入 JuPedSim 人群动力学。
2. 明确定义 guide 对人群速度、期望方向或感知的作用机制。
3. 把静态几何观测升级为时间序列，并记录交互输入。
4. 为动态碰撞、围控保持、瞬态失败和恢复建立独立 evaluator。
5. 在 Step 2 仍保持集中控制和无限通信；局部通信留给 Step 3。

分支约定：`main` 保存已验收基线，`develop` 用于下一阶段集成，功能分支从 `develop` 创建。

## 文档

- [Step 1 最终验收报告](docs/step1_validation.md)
- [Step 1 状态与需求映射](docs/step1_status.md)
- [Step 1 理论、实现和结论边界](docs/step1_theory.md)
- [最终机器可读摘要](experiments/final_validation_summary.json)

## License

本项目采用 [MIT License](LICENSE)。
