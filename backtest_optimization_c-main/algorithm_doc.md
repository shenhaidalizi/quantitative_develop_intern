# 算法逻辑详细文档

## 1. 整体架构

回测系统采用向量化设计，核心思想是**批量并行处理多个权重组合**，避免 Python 循环。

```
输入数据
  ├── 价格序列: prices[t]
  ├── 信号矩阵: signals[t, i]  (时间 x 信号数)
  └── 权重矩阵: weights[i, w]  (信号数 x 权重组合数)

处理流程
  Step 1: 信号组合
    combined[t, w] = Σ(signals[t, i] * weights[i, w])
  
  Step 2: 生成持仓信号
    position[t, w] = sign(combined[t-1, w])  if |combined| > threshold
  
  Step 3: 模拟交易
    cash[t, w], qty[t, w] = update_by_trade_logic()
  
  Step 4: 计算组合价值
    portfolio[t, w] = cash[t, w] + qty[t, w] * prices[t]

输出结果
  ├── 组合价值: portfolio[t, w]
  ├── 收益率: returns[t, w]
  └── 性能指标: sharpe_ratio[w], max_drawdown[w], ...
```

---

## 2. 核心算法详解

### 2.1 信号组合算法

#### 数学公式
给定 T 个时间步，N 个信号，W 个权重组合：

$$
C_{t,w} = \sum_{i=1}^{N} S_{t,i} \cdot W_{i,w}
$$

其中：
- $S_{t,i}$ : 时间 t 信号 i 的值（归一化到 [-1, 1]）
- $W_{i,w}$ : 权重组合 w 中信号 i 的权重（可为任意实数）
- $C_{t,w}$ : 组合后的信号值

#### 伪代码实现
```cpp
// 输入
MatrixXf signals(T, N);    // 信号矩阵
MatrixXf weights(N, W);    // 权重矩阵
float threshold = 0.5;     // 阈值

// 步骤1: 矩阵乘法计算组合信号
MatrixXf combined = signals * weights;  // (T, W)

// 步骤2: 应用阈值生成多空信号
MatrixXi long_short(T, W);
for (int t = 0; t < T; ++t) {
    for (int w = 0; w < W; ++w) {
        if (combined(t, w) > threshold) {
            long_short(t, w) = 1;   // 多头
        } else if (combined(t, w) < -threshold) {
            long_short(t, w) = -1;  // 空头
        } else {
            long_short(t, w) = 0;   // 空仓
        }
    }
}

// 步骤3: 滞后一期生成持仓矩阵（今日信号，明日持仓）
MatrixXi positions = MatrixXi::Zero(T, W);
positions.bottomRows(T-1) = long_short.topRows(T-1);
```

#### 优化要点
1. **矩阵乘法**：使用 Eigen 的 `noalias()` 避免临时变量
   ```cpp
   combined.noalias() = signals * weights;
   ```

2. **阈值判断融合**：一次遍历完成阈值判断和数组移位
   ```cpp
   #pragma omp parallel for collapse(2)
   for (int t = 1; t < T; ++t) {
       for (int w = 0; w < W; ++w) {
           float signal_prev = combined(t-1, w);
           positions(t, w) = (signal_prev > threshold) ? 1 :
                             (signal_prev < -threshold) ? -1 : 0;
       }
   }
   ```

3. **SIMD 向量化**：Eigen 自动使用 SSE/AVX 指令

---

### 2.2 回测引擎算法

#### 交易模式

系统支持三种交易模式：

| 模式            | 说明                           | 买入数量计算                              |
|-----------------|--------------------------------|-------------------------------------------|
| `cash_all`      | 全部可用现金买入               | `qty = cash / price`                      |
| `portfolio_pct` | 组合价值的固定比例分配         | `qty = min(max_pos - curr_pos, cash/price)` |
| `fixed_cash`    | 每次交易固定金额               | `qty = fixed_amount / price`              |

#### 核心循环逻辑

```cpp
void run_backtest(
    const VectorXf& prices,        // (T,) 价格序列
    const MatrixXi& positions,     // (T, W) 持仓信号 (0/1/-1)
    MatrixXf& portfolio_values,    // (T, W) 输出：组合价值
    MatrixXf& cash,                // (T, W) 输出：现金
    MatrixXf& quantities,          // (T, W) 输出：持仓数量
    float initial_cash,
    const std::string& trade_mode,
    float max_allocation_pct = 0.5,
    float fixed_cash_amount = 100000.0
) {
    int T = prices.size();
    int W = positions.cols();
    
    // 初始化
    cash.row(0).setConstant(initial_cash);
    quantities.setZero();
    portfolio_values.row(0).setConstant(initial_cash);
    
    // 计算持仓变化矩阵
    MatrixXi position_changes = MatrixXi::Zero(T, W);
    position_changes.bottomRows(T-1) = positions.bottomRows(T-1) - positions.topRows(T-1);
    
    // 主循环：遍历时间步
    for (int t = 1; t < T; ++t) {
        float price = prices(t);
        
        // 并行处理每个权重组合
        #pragma omp parallel for
        for (int w = 0; w < W; ++w) {
            // 继承前一时刻状态
            cash(t, w) = cash(t-1, w);
            quantities(t, w) = quantities(t-1, w);
            
            int change = position_changes(t, w);
            
            // 买入信号
            if (change > 0) {
                float buy_qty = 0.0f;
                
                if (trade_mode == "cash_all") {
                    buy_qty = cash(t, w) / price;
                }
                else if (trade_mode == "portfolio_pct") {
                    float portfolio_val = cash(t, w) + quantities(t, w) * price;
                    float max_position = portfolio_val * max_allocation_pct / price;
                    float available_cash_qty = cash(t, w) / price;
                    buy_qty = std::min(
                        std::max(0.0f, max_position - quantities(t, w)),
                        available_cash_qty
                    );
                }
                else if (trade_mode == "fixed_cash") {
                    buy_qty = fixed_cash_amount / price;
                }
                
                // 资金约束
                buy_qty = std::min(buy_qty, cash(t, w) / price);
                
                // 更新状态
                cash(t, w) -= buy_qty * price;
                quantities(t, w) += buy_qty;
            }
            // 卖出信号
            else if (change < 0) {
                float sell_qty = quantities(t-1, w);
                cash(t, w) += sell_qty * price;
                quantities(t, w) = 0.0f;
            }
            
            // 更新组合价值
            portfolio_values(t, w) = cash(t, w) + quantities(t, w) * price;
        }
    }
}
```

#### 关键优化技术

1. **OpenMP 并行化**
   - 权重组合之间完全独立，可完美并行
   - 使用 `#pragma omp parallel for` 并行化内层循环
   - 预期线性加速比（4 核 ≈ 3.8x）

2. **内存访问优化**
   - 按行主序访问（C++ 默认）
   - 避免跨行跳跃访问（缓存友好）
   
3. **分支预测优化**
   - 使用 `likely/unlikely` 宏提示编译器
   ```cpp
   if (__builtin_expect(change > 0, 0)) {  // 买入较少见
       // ...
   }
   ```

---

### 2.3 性能指标计算

#### 夏普比率（Sharpe Ratio）

$$
\text{Sharpe} = \frac{\bar{r}}{\sigma_r} \times \sqrt{252}
$$

其中：
- $\bar{r}$ : 日均收益率
- $\sigma_r$ : 收益率标准差
- 252: 年化因子（交易日数）

```cpp
VectorXf calculate_sharpe_ratio(const MatrixXf& portfolio_values) {
    int T = portfolio_values.rows();
    int W = portfolio_values.cols();
    
    // 计算收益率矩阵
    MatrixXf returns(T-1, W);
    for (int t = 0; t < T-1; ++t) {
        returns.row(t) = (portfolio_values.row(t+1).array() / 
                          portfolio_values.row(t).array() - 1.0f);
    }
    
    // 计算均值和标准差
    VectorXf mean_returns = returns.colwise().mean();
    VectorXf std_returns = ((returns.rowwise() - mean_returns.transpose()).array().square()
                            .colwise().sum() / (T-2)).sqrt();
    
    // 夏普比率
    VectorXf sharpe = mean_returns.array() / (std_returns.array() + 1e-8f) * std::sqrt(252.0f);
    
    return sharpe;
}
```

#### 最大回撤（Maximum Drawdown）

$$
\text{MaxDD} = \max_{t_1 < t_2} \frac{V_{t_1} - V_{t_2}}{V_{t_1}}
$$

```cpp
VectorXf calculate_max_drawdown(const MatrixXf& portfolio_values) {
    int T = portfolio_values.rows();
    int W = portfolio_values.cols();
    VectorXf max_dd(W);
    
    #pragma omp parallel for
    for (int w = 0; w < W; ++w) {
        float peak = portfolio_values(0, w);
        float max_drawdown = 0.0f;
        
        for (int t = 1; t < T; ++t) {
            float value = portfolio_values(t, w);
            if (value > peak) {
                peak = value;
            } else {
                float drawdown = (peak - value) / peak;
                if (drawdown > max_drawdown) {
                    max_drawdown = drawdown;
                }
            }
        }
        
        max_dd(w) = max_drawdown;
    }
    
    return max_dd;
}
```

---

## 3. 数据流与内存布局

### 3.1 数据结构设计

```cpp
struct BacktestConfig {
    float initial_cash;
    float max_allocation_pct;
    float fixed_cash_amount;
    float threshold;
    std::string trade_mode;  // "cash_all" / "portfolio_pct" / "fixed_cash"
};

struct BacktestResult {
    MatrixXf portfolio_values;   // (T, W)
    MatrixXf cash_matrix;         // (T, W)
    MatrixXf position_quantities; // (T, W)
    MatrixXf returns;             // (T-1, W)
    VectorXf sharpe_ratios;       // (W,)
    VectorXf max_drawdowns;       // (W,)
};
```

### 3.2 内存管理策略

1. **预分配**：所有输出矩阵在函数入口预分配
   ```cpp
   portfolio_values.resize(T, W);
   cash_matrix.resize(T, W);
   ```

2. **原地更新**：避免临时变量
   ```cpp
   // Bad: 创建临时矩阵
   MatrixXf temp = portfolio_values.col(w) / initial_cash;
   
   // Good: 原地计算
   portfolio_values.col(w).array() /= initial_cash;
   ```

3. **内存池**：高频调用场景使用对象池复用内存
   ```cpp
   class BacktestEngine {
       MatrixXf buffer_portfolio_;
       MatrixXf buffer_cash_;
       // ... 成员变量作为缓冲区
   };
   ```

### 3.3 缓存优化

**行主序访问**（Eigen 默认）
```cpp
// Good: 按行遍历（连续内存）
for (int t = 0; t < T; ++t) {
    for (int w = 0; w < W; ++w) {
        data(t, w) = ...;
    }
}

// Bad: 按列遍历（跳跃访问）
for (int w = 0; w < W; ++w) {
    for (int t = 0; t < T; ++t) {
        data(t, w) = ...;  // 缓存不友好
    }
}
```

---

## 4. 边界条件处理

### 4.1 数值稳定性

```cpp
// 避免除零
float sharpe = mean_return / (std_return + 1e-8f);

// 避免负数开方
float std = std::sqrt(std::max(0.0f, variance));

// 避免 log(0)
float log_return = std::log(std::max(1e-10f, price_ratio));
```

### 4.2 异常情况

| 异常情况              | 处理策略                           |
|-----------------------|------------------------------------|
| 价格序列包含 NaN      | 抛出异常 `invalid_argument`        |
| 初始资金为负          | 抛出异常                           |
| 权重矩阵维度不匹配    | 抛出异常                           |
| 时间步数为 0          | 返回空结果                         |
| 权重组合数为 0        | 返回空结果                         |

---

## 5. 算法复杂度分析

### 5.1 时间复杂度

| 模块                | 复杂度                    | 说明                       |
|---------------------|---------------------------|----------------------------|
| 信号组合            | O(T × N × W)              | 矩阵乘法                   |
| 回测引擎            | O(T × W)                  | 双重循环                   |
| 性能指标            | O(T × W)                  | 统计计算                   |
| **总计**            | **O(T × max(N, 1) × W)**  | 瓶颈在回测引擎             |

### 5.2 空间复杂度

| 数据结构            | 大小              | 示例（T=1000, W=10000） |
|---------------------|-------------------|-------------------------|
| 价格序列            | O(T)              | ~4 KB                   |
| 信号矩阵            | O(T × N)          | ~40 KB (N=10)           |
| 权重矩阵            | O(N × W)          | ~400 KB                 |
| 组合价值矩阵        | O(T × W)          | ~40 MB                  |
| **峰值内存**        | **O(T × W)**      | **~120 MB**             |

---

## 6. 示例计算流程

### 输入数据
```
prices = [100, 101, 102, 101, 103]  # 5 个时间步
signals = [[0.5, 0.3],               # 2 个信号
           [0.6, 0.2],
           [0.4, 0.1],
           [-0.3, 0.5],
           [-0.5, 0.6]]
weights = [[0.7, 0.3],               # 2 个权重组合
           [0.3, 0.7]]
threshold = 0.4
initial_cash = 10000
```

### Step 1: 信号组合
```
combined = signals @ weights
         = [[0.5*0.7 + 0.3*0.3, 0.5*0.3 + 0.3*0.7],
            [0.6*0.7 + 0.2*0.3, 0.6*0.3 + 0.2*0.7],
            ...]
         = [[0.44, 0.36],
            [0.48, 0.32],
            [0.31, 0.19],
            [-0.06, 0.26],
            [-0.17, 0.27]]
```

### Step 2: 持仓信号
```
long_short (t) = sign(combined(t)) if |combined(t)| > 0.4
               = [[1, 0],
                  [1, 0],
                  [0, 0],
                  [0, 0],
                  [0, 0]]

positions (t) = long_short(t-1)  # 滞后一期
              = [[0, 0],
                 [1, 0],
                 [1, 0],
                 [0, 0],
                 [0, 0]]
```

### Step 3: 回测
```
t=0: cash=[10000, 10000], qty=[0, 0], value=[10000, 10000]
t=1: position_change=[1, 0]
     → 买入: qty[0] = 10000/101 = 99.01
     → cash=[0, 10000], qty=[99.01, 0], value=[10000, 10000]
t=2: position_change=[0, 0] (持有)
     → cash=[0, 10000], qty=[99.01, 0], value=[10099, 10000]
t=3: position_change=[-1, 0]
     → 卖出: cash[0] = 99.01 * 101 = 10000
     → cash=[10000, 10000], qty=[0, 0], value=[10000, 10000]
...
```

### Step 4: 性能指标
```
returns = [[0.0099, 0.0],
           [-0.0099, 0.0],
           [0.0, 0.0]]
sharpe_ratio = [mean(returns) / std(returns) * sqrt(252)]
             ≈ [0.0, 0.0]  # 收益率为0
```

---

## 7. 参考文献

1. **向量化回测**: VectorBT - https://github.com/polakowo/vectorbt
2. **矩阵运算优化**: Eigen 文档 - https://eigen.tuxfamily.org/dox/TopicWritingEfficientProductExpression.html
3. **OpenMP 并行模式**: https://www.openmp.org/wp-content/uploads/OpenMP-API-Specification-5-2.pdf
4. **金融指标计算**: Quantlib - https://www.quantlib.org/

