<div align="center">
  <img src="docs/assets/abcg-hero.svg" width="100%" alt="ABCG Controller — guide agents deployed around a static crowd" />
</div>

<div align="center">
  <br />
  <a href="docs/step1_validation.md"><img src="https://img.shields.io/badge/Step_1-CLOSED-20b8a6?style=for-the-badge" alt="Step 1 CLOSED" /></a>
  <a href="https://github.com/Wu-kaixin/ABCG-controller/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Wu-kaixin/ABCG-controller/ci.yml?branch=main&amp;style=for-the-badge&amp;label=tests" alt="CI status" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&amp;logo=python&amp;logoColor=white" alt="Python 3.12+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-5b7cfa?style=for-the-badge" alt="MIT License" /></a>
</div>

<p align="center">
  <strong>在未知人群轮廓外，安全、可复现地部署引导代理。</strong><br />
  <sub>Safe, reproducible guide-agent deployment around an unknown crowd boundary.</sub>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-可视化生成与回放">可视化</a> ·
  <a href="#-系统架构">系统架构</a> ·
  <a href="#-方法与协议">方法与协议</a> ·
  <a href="#-验证证据">验证证据</a> ·
  <a href="#-step-2-路线图">Step 2</a>
</p>

---

ABCG Controller 是一个面向人群围控研究的可审计实验框架。当前版本完成了 **Step 1：单个静态人群、无 guide–crowd 动力学交互、无通信限制**，涵盖边界估计、周期部署、绕障分配、安全运动、停滞恢复以及从落盘轨迹出发的独立验收。

<table>
  <tr>
    <td width="25%" align="center"><strong>7,216 / 7,216</strong><br /><sub>冻结任务完成</sub></td>
    <td width="25%" align="center"><strong>0</strong><br /><sub>实验执行错误</sub></td>
    <td width="25%" align="center"><strong>7,216 / 7,216</strong><br /><sub>离线复判一致</sub></td>
    <td width="25%" align="center"><strong>29 / 29</strong><br /><sub>测试通过</sub></td>
  </tr>
</table>

> [!NOTE]
> **CLOSED 是有边界的工程结论。** 它不表示动态人群遏制、真实机器人安全、全局最优或任意初态必达。精确定义见[理论与结论边界](docs/step1_theory.md)。

## ✨ 为什么使用 ABCG

| | 能力 | 说明 |
|---|---|---|
| 🧭 | **保守几何建模** | 从带半径的人群观测构建占据包络和安全部署曲线 |
| ⚙️ | **多种部署策略** | Equal Arc、Average CVT、Mass CVT、DistMesh-inspired |
| 🛡️ | **连续区间安全复核** | 检查 guide–guide、guide–human 与 guide–wall 净间距 |
| 🧩 | **静态绕障分配** | visibility graph、Dijkstra、路径代价匹配与可达性检查 |
| 🔁 | **有限停滞恢复** | 路径重算 → 可达重分配 → 确定性优先级让行 |
| 🔬 | **独立轨迹验收** | 不相信 controller 的内部成功标志，从保存轨迹重算九类 criteria |
| 🔐 | **可追溯与可恢复** | commit/source/config/input/task hash、原子状态与安全 resume |

## 🚀 快速开始

需要 **Python 3.12+**。

```bash
git clone https://github.com/Wu-kaixin/ABCG-controller.git
cd ABCG-controller
python -m venv .venv
```

<details open>
<summary><strong>Linux / macOS</strong></summary>

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python run.py --config configs/step1/square.yaml --output results/quickstart
```

</details>

<details>
<summary><strong>Windows PowerShell</strong></summary>

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python run.py --config configs/step1/square.yaml --output results/quickstart
```

</details>

一次运行会在 `--output` 目录写入可回放的证据包。默认还会生成 `scene.png`。

## 🎥 可视化：生成与回放

实验结果和实时演示是分开的。`run.py` 负责落盘；`live_demo.py` 负责并排看仿真；已经保存的目录用 `visualization.py` 和 `--reevaluate` 回放，不必重跑控制器。

### 生成文件

| 产物 | 命令 |
|---|---|
| 单次实验（JSON / NPZ / YAML / `scene.png`） | `python run.py --config configs/step1/square.yaml --output results/quickstart` |
| 只要轨迹、不要图 | 追加 `--no-plots` |
| 多 seed 批量 | `python run.py --config configs/step1/square.yaml --output results/batch --seeds 0 1 2 3 4 --workers auto` |
| 实时四宫格（当前屏幕最大化） | `python live_demo.py` |
| 六组场景同时演示 | `python live_demo.py --all` |
| 指定场景 | `python live_demo.py --cases square,ellipse,off_center` |
| 静态对比 PNG | `python live_demo.py --all --snapshot results/live_demo.png` |
| 动画 GIF | `python live_demo.py --all --gif results/live_demo_all.gif` |

`live_demo.py` 内置场景：`square`、`rectangle`、`ellipse`、`off_center`、`elongated`、`high_demand`。窗口在鼠标所在显示器最大化；空格暂停，`F11` 全屏，`Q` 关闭。`--stride` 控制每帧推进的仿真步数，`--interval` 控制 GIF/动画帧间隔（毫秒）。

每个实验输出目录包含：

| 文件 | 内容 |
|---|---|
| `config.yaml` | 实际使用的 Step 1 配置快照 |
| `trajectory.npz` | 时间、guide 轨迹、人群、边界、目标和 assignment |
| `metrics.json` | 终止状态、九类 criteria、安全与规划诊断、task hash |
| `planning.json` | 有界覆盖搜索的逐候选记录 |
| `state.json` | 原子完成标记，供 `--resume` 使用 |
| `scene.png` | 运行结束时的场景图（除非 `--no-plots`） |

### 回放文件

不重新仿真，只读已经保存的证据：

```bash
# 从 trajectory.npz 重算九类验收条件
python run.py --reevaluate results/quickstart

# 从保存轨迹重绘场景图（可另存）
python visualization.py --result results/quickstart
python visualization.py --result results/quickstart --output results/quickstart/scene_from_saved.png
```

GIF 和实时窗口是演示产物，不能代替实验回放。要复查一次实验，使用上面的 `--reevaluate` 和 `visualization.py --result`。批量结果可以：

```bash
python experiments/validation_runner.py --output results/validation --reevaluate
python experiments/validation_runner.py --output results/validation --plot-only
```

## 🧠 系统架构

```mermaid
flowchart LR
    CFG["YAML<br/>场景与实验"] --> ENV["Environment<br/>静态人群"]
    ENV --> OBS["Global<br/>Observation"]
    OBS --> GEO["Boundary<br/>保守包络"]
    GEO --> PLAN["Coverage<br/>周期部署"]
    PLAN --> NAV["Navigation<br/>绕障匹配"]
    NAV --> CTRL["Controller<br/>跟踪与恢复"]
    CTRL --> SAFE["Safety<br/>速度过滤"]
    SAFE --> TRAJ["Trajectory<br/>持久化"]
    TRAJ --> EVAL["Evaluator<br/>独立复判"]
    EVAL --> OUT["JSON · CSV<br/>图表 · 状态"]
    SAFE -. guide feedback .-> CTRL

    classDef input fill:#12283a,stroke:#4b88b5,color:#e9f7ff;
    classDef core fill:#103b3c,stroke:#35c8bb,color:#ebfffd;
    classDef evidence fill:#372b48,stroke:#a485d8,color:#f8f2ff;
    class CFG,ENV,OBS input;
    class GEO,PLAN,NAV,CTRL,SAFE core;
    class TRAJ,EVAL,OUT evidence;
```

### Step 1 的系统假设

| 人群 | 交互 | 观测 | 通信 | 环境 |
|---|---|---|---|---|
| 单个、静态 | guide 不改变人群动力学 | 全局快照 | 集中且不受限 | 已知封闭场地 |

## 🧮 方法与协议

### 部署方法

| 方法 | CLI | 主要用途 |
|---|---|---|
| **Equal Arc** | `equal_arc` | 沿部署曲线等弧长分布 |
| **Average CVT** | `average_cvt` | 几何密度驱动的周期 CVT |
| **Mass CVT** | `mass_cvt` | demand 权重驱动的覆盖分布 |
| **DistMesh-inspired** | `distmesh` | 相邻间距均衡迭代 |

### 资源协议

```bash
# 在资源上限内有界搜索 guide 数量
python run.py --config configs/step1/square.yaml --output results/adaptive \
  --method equal_arc --protocol adaptive_resource

# 固定 guide 数量，适合公平方法对照
python run.py --config configs/step1/square.yaml --output results/fixed-24 \
  --method equal_arc --protocol fixed_n --fixed-n 24
```

多 seed 并行：

```bash
python run.py --config configs/step1/square.yaml --output results/batch \
  --seeds 0 1 2 3 4 --workers auto --no-plots
```

追加 `--resume` 可继续中断任务。只有全部复现哈希匹配且结果完整的任务才会跳过。

## ✅ 验证证据

| Gate | 结果 |
|---|---:|
| 单元、集成与反例测试 | **29/29 PASS** |
| 最终冻结任务 | **7216/7216 completed** |
| 冻结终止语义 | **7216/7216 matched** |
| 实验执行错误 | **0** |
| 保存轨迹离线复判 | **7216/7216 consistent** |
| 缺失 task hash | **0** |
| 净安全间距低于 `-1e-7` | **0** |

其中 5342 个任务以 `SUCCESS` 结束；其余任务诚实保留为结构化的容量不足、非法偏移、路径不可达、初始化无效或规划搜索耗尽，而不是被删除或包装成成功。

<p align="center">
  <a href="docs/step1_validation.md"><strong>阅读完整验收报告 →</strong></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="experiments/final_validation_summary.json">查看机器摘要</a>
</p>

<details>
<summary><strong>复现验证矩阵</strong></summary>

```bash
python -m pytest -q
python experiments/validation_runner.py --output results/smoke \
  --phase development --smoke --workers auto
python experiments/validation_runner.py --output results/development \
  --phase development --workers auto
python experiments/validation_runner.py --output results/validation \
  --phase validation --workers auto
python experiments/validation_runner.py --output results/validation --reevaluate
python experiments/validation_runner.py --output results/validation --plot-only
```

完整矩阵计算量较大。冻结的场景、seed、方法、协议和 gates 见 [`acceptance_manifest.yaml`](experiments/acceptance_manifest.yaml)。

</details>

## 🗺️ Step 2 路线图

`main` 保存已验收的 Step 1 基线，`develop` 是 Step 2 的集成分支。

```mermaid
flowchart LR
    S1["Step 1<br/>静态人群<br/>CLOSED"] --> S2A["动态人群<br/>JuPedSim advance"]
    S2A --> S2B["guide–crowd<br/>交互模型"]
    S2B --> S2C["动态安全与<br/>围控 evaluator"]
    S2C --> S2["Step 2<br/>冻结验证"]
    S2 --> S3["Step 3<br/>局部观测与通信"]

    classDef done fill:#103b3c,stroke:#35c8bb,color:#ebfffd;
    classDef next fill:#12283a,stroke:#4b88b5,color:#e9f7ff;
    classDef future fill:#2c2c3e,stroke:#777799,color:#eeeeff;
    class S1 done;
    class S2A,S2B,S2C,S2 next;
    class S3 future;
```

Step 2 仍保持全局观测和无限通信；局部观测与邻居通信属于 Step 3。

## 📁 仓库导航

<table>
  <tr>
    <td><a href="controller"><strong>controller/</strong></a><br /><sub>边界、覆盖、导航、安全和总体控制</sub></td>
    <td><a href="configs/step1"><strong>configs/step1/</strong></a><br /><sub>基准场景与验收夹具</sub></td>
  </tr>
  <tr>
    <td><a href="experiments"><strong>experiments/</strong></a><br /><sub>冻结 manifest、runner 与机器摘要</sub></td>
    <td><a href="tests"><strong>tests/</strong></a><br /><sub>单元、集成和反例测试</sub></td>
  </tr>
  <tr>
    <td><a href="evaluator.py"><strong>evaluator.py</strong></a><br /><sub>与 controller 解耦的轨迹验收</sub></td>
    <td><a href="run.py"><strong>run.py</strong></a><br /><sub>单次、批量、resume 与复判入口</sub></td>
  </tr>
  <tr>
    <td><a href="live_demo.py"><strong>live_demo.py</strong></a><br /><sub>多场景实时对照、PNG 与 GIF</sub></td>
    <td><a href="visualization.py"><strong>visualization.py</strong></a><br /><sub>从已保存轨迹重绘场景</sub></td>
  </tr>
</table>

### 深入阅读

- [Step 1 最终验收报告](docs/step1_validation.md)
- [Step 1 状态与需求映射](docs/step1_status.md)
- [理论、实现和结论边界](docs/step1_theory.md)
- [机器可读验证摘要](experiments/final_validation_summary.json)

---

<p align="center">
  Built for reproducible crowd-guidance research.<br />
  Released under the <a href="LICENSE">MIT License</a>.
</p>
