# ABCG-controller

**Adaptive Guide-Agent Deployment for Unknown Dynamic Crowds**

当前实现 Step 1：在封闭场地中，围绕一个静态、未知轮廓的人群部署外部引导代理。人群不受引导代理影响；观测为全局，通信不受限。

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
| `controller/coverage.py` | 按需求权重进行弧长 CVT 规划 |
| `controller/safety.py` | 速度安全过滤与运动路径检查 |
| `interfaces.py` | 观测数据和未来局部控制接口 |
| `run.py` | 读取配置、运行仿真、保存结果 |
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

每次使用空的结果目录。输出只有四项：`config.yaml`、`metrics.json`、`trajectory.npz`、`scene.png`。

多个随机种子可以并行运行：

```bash
python run.py --config configs/step1/square.yaml --output results/batch --seeds 0 1 2 3 4 --workers auto --no-plots
```

## 当前模型

1. JuPedSim 生成人群位置后保持固定；引导代理通过速度输入逐步移动。
2. 房间边界已知；人群生成区域仅环境使用，控制器只能获得观测点和个体属性。
3. 最小边界模型采用观测点的**凸包**，再向外偏移生成部署曲线。它对凹形人群采用保守包络，不恢复凹陷细节。
4. 代理数量按部署曲线长度和 `target_gap` 选择；CVT 根据需求密度规划目标，再分配给各引导代理。多余代理作为备用。
5. 人体半径影响初始化间距和安全距离；`demand` 权重影响部署分布。两种属性均可在配置中调整，设 `std: 0` 可进行同质性对照。
6. 速度经过安全过滤后执行；同时检查步间直线运动路径。非法部署、资源不足或超时均明确报告失败。

`target_gap` 是平均间距预算，最终最大间隙单独报告。`success` 表示安全到达部署目标，尚不表示动态人群遏制、真实机器人安全或全局最优。

## 从哪里开始修改

- **改场景和参数**：修改两个 YAML 文件。
- **改人群边界模型**：替换 `controller/boundary.py` 中的估计函数。
- **改部署策略或控制律**：修改 `controller/coverage.py` 或 `controller/abcg.py`。
- **加入新场景**：扩展 `scene.py` 的 `SCENES`。非矩形场地还需相应的墙壁安全约束。
- **Step 2 动态人群**：扩展 `Environment.advance()`，接入 JuPedSim 动力学及引导交互。
- **Step 3 去中心化**：实现 `interfaces.py` 中的 `LocalPolicy`，加入局部观测和邻居通信。

当前只实现 Step 1，Step 2、Step 3 为扩展入口。
