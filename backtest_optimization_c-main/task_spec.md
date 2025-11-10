# 任务规格说明书

## 1. 项目概述

### 1.1 项目目标
将 Python 回测系统的性能瓶颈模块使用 C++ 重写，通过 Pybind11 提供 Python 接口，保持 API 兼容性的同时实现显著的性能提升。

### 1.2 优化原因
当前 Python 实现在大规模权重优化场景下性能不足：
- 单次优化需要评估 10000+ 个权重组合
- 每个权重组合需要遍历 1000+ 个时间步
- 遗传算法/梯度优化需要多代迭代
- 总计算量：O(权重数 × 时间步数 × 迭代次数) ≈ 10^7 - 10^9 次运算

### 1.3 技术选型
- **C++17**: 现代 C++ 特性，性能与可维护性平衡
- **Pybind11**: 零成本的 Python-C++ 绑定
- **Eigen3**: 高性能线性代数库，接口友好
- **OpenMP**: 共享内存并行，简单高效

## 2. 核心模块详细说明

### 2.1 模块一：回测引擎核心 (BacktestEngine)

#### 功能描述
对多个权重组合同时进行向量化回测，计算每个权重组合的持仓、现金流和组合价值。

#### 当前 Python 实现位置
```
文件: src/trader_backtest/engine/candle.py
方法: CandleEngine.run_multi_weight()
行数: 305-450
```

#### 核心算法伪代码
```python
def run_multi_weight(prices, position_matrix, n_weights, initial_cash, trade_mode):
    """
    输入:
        prices: (n_timesteps,) - 价格序列
        position_matrix: (n_timesteps, n_weights) - 持仓信号矩阵 (0/1/-1)
        n_weights: 权重组合数量
        initial_cash: 初始资金
        trade_mode: 交易模式 ("cash_all", "portfolio_pct", "fixed_cash")
    
    输出:
        portfolio_values: (n_timesteps, n_weights) - 组合价值矩阵
        cash_matrix: (n_timesteps, n_weights) - 现金矩阵
        position_qty_matrix: (n_timesteps, n_weights) - 持仓数量矩阵
    """
    
    # 初始化
    cash_matrix = np.zeros((n_timesteps, n_weights))
    position_qty_matrix = np.zeros((n_timesteps, n_weights))
    portfolio_values = np.zeros((n_timesteps, n_weights))
    
    cash_matrix[0, :] = initial_cash
    portfolio_values[0, :] = initial_cash
    
    # 计算持仓变化
    position_changes = np.diff(position_matrix, axis=0, prepend=0)
    
    # 逐时间步更新
    for t in range(1, n_timesteps):
        # 继承前一时刻状态
        cash_matrix[t] = cash_matrix[t-1]
        position_qty_matrix[t] = position_qty_matrix[t-1]
        
        price = prices[t]
        change = position_changes[t]  # (n_weights,)
        
        # 买入信号处理
        buy_mask = change > 0
        if buy_mask.any():
            if trade_mode == "cash_all":
                # 全部现金买入
                buy_qty = cash_matrix[t, buy_mask] / price
            elif trade_mode == "portfolio_pct":
                # 组合百分比分配
                portfolio_val = cash_matrix[t] + position_qty_matrix[t] * price
                max_position = portfolio_val * max_allocation_pct
                buy_qty = max(0, min(
                    max_position - position_qty_matrix[t],
                    cash_matrix[t] / price
                ))
            elif trade_mode == "fixed_cash":
                # 固定金额
                buy_qty = fixed_cash_amount / price
            
            buy_qty = min(buy_qty, cash_matrix[t] / price)  # 资金约束
            cash_matrix[t, buy_mask] -= buy_qty * price
            position_qty_matrix[t, buy_mask] += buy_qty
        
        # 卖出信号处理
        sell_mask = change < 0
        if sell_mask.any():
            sell_qty = position_qty_matrix[t-1, sell_mask]
            cash_matrix[t, sell_mask] += sell_qty * price
            position_qty_matrix[t, sell_mask] = 0
        
        # 更新组合价值
        portfolio_values[t] = cash_matrix[t] + position_qty_matrix[t] * price
    
    return portfolio_values, cash_matrix, position_qty_matrix
```

#### 性能瓶颈分析
1. **Python 循环**: 外层时间步循环（1000+ 次）
2. **NumPy 索引**: 大量布尔索引操作
3. **内存分配**: 每次迭代的临时数组创建

#### 优化策略
1. 使用 C++ 循环替代 Python 循环
2. 消除中间临时变量，原地更新
3. 利用 CPU 缓存，改进内存访问模式
4. OpenMP 并行化权重维度（每个权重组合独立）

#### 预期性能提升
- 单线程: 30-50x
- 4 线程: 80-120x
- 8 线程: 120-200x

---

### 2.2 模块二：信号组合处理器 (SignalProcessor)

#### 功能描述
将多个信号按权重组合，生成多头/空头信号和持仓矩阵。

#### 当前 Python 实现位置
```
文件: src/trader_backtest/strategy/signal_strategy.py
方法: SignalCombinationStrategy.process_dataframe()
行数: 119-186
```

#### 核心算法伪代码
```python
def process_signals(signal_matrix, weights_matrix, threshold):
    """
    输入:
        signal_matrix: (n_timesteps, n_signals) - 信号值矩阵
        weights_matrix: (n_signals, n_weights) - 权重矩阵
        threshold: float - 信号阈值
    
    输出:
        combined_signals: (n_timesteps, n_weights) - 组合信号
        long_short_matrix: (n_timesteps, n_weights) - 多空信号 (1/0/-1)
        position_matrix: (n_timesteps, n_weights) - 持仓矩阵 (1/0/-1)
    """
    
    # 矩阵乘法: 信号加权组合
    combined_signals = signal_matrix @ weights_matrix  # (n_timesteps, n_weights)
    
    # 生成多空信号
    long_short_matrix = np.zeros_like(combined_signals, dtype=np.int8)
    long_short_matrix[combined_signals > threshold] = 1
    long_short_matrix[combined_signals < -threshold] = -1
    
    # 持仓矩阵: 滞后一期（今日信号，明日持仓）
    position_matrix = np.zeros_like(long_short_matrix)
    position_matrix[1:] = long_short_matrix[:-1]
    
    return combined_signals, long_short_matrix, position_matrix
```

#### 性能瓶颈分析
1. **矩阵乘法**: NumPy 调用 BLAS，已较优但仍有优化空间
2. **阈值判断**: 两次完整矩阵遍历
3. **数组移位**: `position_matrix[1:] = long_short_matrix[:-1]` 涉及内存拷贝

#### 优化策略
1. 使用 Eigen 的矩阵乘法（编译期优化）
2. 融合阈值判断和数组移位为单次遍历
3. SIMD 指令加速（Eigen 自动向量化）

#### 预期性能提升
- 单线程: 5-10x
- 多线程: 10-20x

---

### 2.3 模块三：优化器核心 (OptimizerKernel)

#### 功能描述
批量评估多个权重组合，计算每个组合的夏普比率或其他指标。

#### 当前 Python 实现位置
```
文件: src/trader_backtest/optimizer/candle_weight_optimizer.py
方法: CandleWeightOptimizer.evaluate_weights()
行数: 97-113
```

#### 核心算法伪代码
```python
def evaluate_weights_batch(weights_batch, signal_matrix, prices, initial_cash):
    """
    输入:
        weights_batch: (n_signals, n_candidates) - 候选权重矩阵
        signal_matrix: (n_timesteps, n_signals) - 信号矩阵
        prices: (n_timesteps,) - 价格序列
        initial_cash: 初始资金
    
    输出:
        scores: (n_candidates,) - 每个权重组合的评分（如夏普比率）
    """
    
    # 步骤1: 信号组合
    combined_signals, _, position_matrix = process_signals(
        signal_matrix, weights_batch, threshold
    )
    
    # 步骤2: 回测
    portfolio_values, _, _ = run_multi_weight(
        prices, position_matrix, n_candidates, initial_cash, trade_mode
    )
    
    # 步骤3: 计算收益率
    returns = np.diff(portfolio_values, axis=0) / portfolio_values[:-1]
    
    # 步骤4: 计算夏普比率
    mean_returns = returns.mean(axis=0)
    std_returns = returns.std(axis=0)
    sharpe_ratios = mean_returns / (std_returns + 1e-8) * np.sqrt(252)
    
    return sharpe_ratios
```

#### 性能瓶颈分析
1. **重复调用**: 优化过程中需调用数千次
2. **跨模块调用开销**: Python 函数调用成本高
3. **中间结果分配**: 大量临时数组创建

#### 优化策略
1. 将三个模块整合为单一 C++ 函数
2. 复用内存缓冲区
3. 流水线优化：信号处理 → 回测 → 指标计算

#### 预期性能提升
- 单线程: 20-30x
- 多线程: 60-100x

---

## 3. 接口设计

### 3.1 Python 接口要求

所有 C++ 函数必须通过 Pybind11 暴露为 Python 函数，接受 NumPy 数组作为输入输出。

#### 示例接口
```python
import backtest_cpp

# 模块1: 回测引擎
portfolio_values, cash, positions = backtest_cpp.run_backtest(
    prices,              # np.ndarray (n_timesteps,)
    position_matrix,     # np.ndarray (n_timesteps, n_weights)
    initial_cash,        # float
    trade_mode,          # str: "cash_all" / "portfolio_pct" / "fixed_cash"
    max_allocation_pct,  # float (仅 portfolio_pct 模式)
    fixed_cash_amount    # float (仅 fixed_cash 模式)
)

# 模块2: 信号处理
combined_signals, long_short, positions = backtest_cpp.process_signals(
    signal_matrix,   # np.ndarray (n_timesteps, n_signals)
    weights_matrix,  # np.ndarray (n_signals, n_weights)
    threshold        # float
)

# 模块3: 批量评估
scores = backtest_cpp.evaluate_weights_batch(
    weights_batch,   # np.ndarray (n_signals, n_candidates)
    signal_matrix,   # np.ndarray (n_timesteps, n_signals)
    prices,          # np.ndarray (n_timesteps,)
    initial_cash,    # float
    trade_mode,      # str
    threshold        # float
)
```

### 3.2 数据类型映射

| Python (NumPy)  | C++ (Eigen)              | 说明                |
|-----------------|--------------------------|-------------------|
| `np.float32`    | `Eigen::MatrixXf`        | 单精度浮点矩阵      |
| `np.float64`    | `Eigen::MatrixXd`        | 双精度浮点矩阵      |
| `np.int8`       | `Eigen::MatrixXi`        | 整型矩阵           |
| `(n,)`          | `Eigen::VectorXf`        | 一维向量           |
| `(n, m)`        | `Eigen::MatrixXf`        | 二维矩阵           |

### 3.3 错误处理

C++ 代码应使用异常处理，Pybind11 会自动将 C++ 异常转换为 Python 异常。

```cpp
if (weights.cols() != signal_matrix.cols()) {
    throw std::invalid_argument("权重矩阵维度不匹配");
}
```

---

## 4. 测试要求

### 4.1 单元测试
- 每个模块至少 5 个测试用例
- 边界条件测试（空数组、单元素、超大数组）
- 数值精度测试（与 Python 结果误差 < 1e-6）

### 4.2 集成测试
- 完整回测流程端到端测试
- 与现有 Python 代码对比测试

### 4.3 性能测试
- 不同数据规模性能测试（100, 1000, 10000 时间步）
- 不同权重数性能测试（10, 100, 1000, 10000 权重）
- 多线程扩展性测试（1, 2, 4, 8 线程）

---

## 5. 交付物清单

### 5.1 源代码
- [ ] C++ 实现（.cpp / .h）
- [ ] Pybind11 绑定代码
- [ ] CMakeLists.txt 构建脚本
- [ ] setup.py（Python 安装脚本）

### 5.2 测试代码
- [ ] C++ 单元测试（Google Test 或 Catch2）
- [ ] Python 集成测试
- [ ] 性能基准测试脚本

### 5.3 文档
- [ ] 代码注释（Doxygen 格式）
- [ ] 编译安装指南
- [ ] API 使用文档
- [ ] 性能测试报告

---

## 6. 开发流程

### 6.1 阶段一：环境搭建 (1-2 天)
- [ ] 安装开发工具链
- [ ] 配置 Pybind11 + Eigen
- [ ] 搭建最小可编译项目

### 6.2 阶段二：模块实现 (7-10 天)
- [ ] 实现 SignalProcessor (简单，先做)
- [ ] 实现 BacktestEngine (核心，重点)
- [ ] 实现 OptimizerKernel (整合前两者)

### 6.3 阶段三：测试优化 (3-5 天)
- [ ] 单元测试 + 修复 Bug
- [ ] 性能测试 + 优化瓶颈
- [ ] 多线程并行化

### 6.4 阶段四：交付 (1-2 天)
- [ ] 代码审查 + 重构
- [ ] 文档完善
- [ ] 打包发布

---

## 7. 常见问题

### Q1: 必须使用 Eigen 吗？
A: 不强制，但推荐。可以使用 ArrayFire、Armadillo 或纯 C++ 数组。

### Q2: 支持 GPU 加速吗？
A: 当前阶段不要求 GPU，CPU 优化优先。未来可考虑 CUDA。

### Q3: 如何保证数值精度？
A: 使用 `double` 而非 `float`，并与 Python 参考实现逐步对比。

### Q4: 性能未达标怎么办？
A: 提供性能分析报告（Perf / VTune），指出瓶颈，协商调整目标。

