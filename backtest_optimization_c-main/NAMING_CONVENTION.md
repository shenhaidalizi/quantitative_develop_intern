# 命名规范和版本对比

## 目的

为了方便将 Python 代码迁移到 C++，统一命名规范，并提供原版代码用于性能对比。

---

## Python 参考实现版本对比

### 两个版本

| 版本 | 文件 | 特点 | 用途 |
|------|------|------|------|
| **简化版** | `core_engine.py` | 双重循环，逻辑清晰 | C++ 开发参考 |
| **向量化版** | `core_engine_vectorized.py` | NumPy 向量化，原版逻辑 | 性能对比基准 |

### 函数名对应关系

| 原始代码 (backtest-dev) | 简化版 | 向量化版 | C++ 接口 |
|-------------------------|--------|----------|----------|
| `run_multi_weight()` | `run_backtest_python()` | `run_multi_weight_vectorized()` | `run_backtest()` |
| `process_dataframe()` | `process_signals_python()` | `process_signals_python()` | `process_signals()` |

### 变量名对应关系

| 原始代码 | 简化版 | 向量化版 | C++ 变量名 |
|----------|--------|----------|-----------|
| `n_timestamps` | `n_timesteps` | `n_timestamps` | `n_timesteps` |
| `real_position_matrix` | `quantity_matrix` | `real_position_matrix` | `quantity_matrix` |
| `portfolio_value_matrix` | `portfolio_values` | `portfolio_value_matrix` | `portfolio_values` |
| `position_change_matrix` | `position_changes` | `position_change_matrix` | `position_changes` |

---

## 统一命名规范（用于 C++）

### 1. 函数命名

**规则**: 使用 `snake_case`，动词开头

```cpp
// ✅ 推荐
void run_backtest(...)
void process_signals(...)
void calculate_sharpe_ratio(...)

// ❌ 不推荐
void RunBacktest(...)
void processSignals(...)
```

### 2. 变量命名

**规则**: 使用 `snake_case`，名词为主

```cpp
// ✅ 推荐
MatrixXf portfolio_values;
MatrixXf cash_matrix;
MatrixXf quantity_matrix;
VectorXf prices;
int n_timesteps;
int n_weights;

// ❌ 不推荐
MatrixXf portfolioValues;
MatrixXf CashMatrix;
MatrixXf real_position_matrix;  // 过长，改为 quantity_matrix
```

### 3. 常量命名

**规则**: 使用 `UPPER_SNAKE_CASE`

```cpp
const float INITIAL_CASH = 1000000.0f;
const float MAX_ALLOCATION_PCT = 0.5f;
const int DEFAULT_TIMESTEPS = 1000;
```

### 4. 类型命名

**规则**: 使用 `PascalCase`

```cpp
class BacktestEngine;
class SignalProcessor;
class MetricsCalculator;
struct BacktestConfig;
enum class TradeMode;
```

---

## 参数名统一

### 回测引擎参数

| 参数 | Python 类型 | C++ 类型 | 说明 |
|------|------------|---------|------|
| `prices` | `np.ndarray (n,)` | `VectorXf` | 价格序列 |
| `position_matrix` | `np.ndarray (n, m)` | `MatrixXi` | 持仓信号 {-1,0,1} |
| `initial_cash` | `float` | `float` | 初始资金 |
| `trade_mode` | `str` | `TradeMode` enum | 交易模式 |
| `max_allocation_pct` | `float` | `float` | 最大仓位比例 |
| `fixed_cash_amount` | `float` | `float` | 固定交易金额 |

**返回值**:
```python
# Python
portfolio_values, cash_matrix, quantity_matrix = run_backtest(...)

# C++
std::tuple<MatrixXf, MatrixXf, MatrixXf> result = run_backtest(...);
auto [portfolio_values, cash_matrix, quantity_matrix] = result;
```

### 信号处理参数

| 参数 | Python 类型 | C++ 类型 | 说明 |
|------|------------|---------|------|
| `signal_matrix` | `np.ndarray (n, m)` | `MatrixXf` | 信号矩阵 |
| `weights_matrix` | `np.ndarray (m, k)` | `MatrixXf` | 权重矩阵 |
| `threshold` | `float` | `float` | 信号阈值 |

**返回值**:
```python
# Python
combined_signals, long_short_matrix, position_matrix = process_signals(...)

# C++
std::tuple<MatrixXf, MatrixXi, MatrixXi> result = process_signals(...);
auto [combined, long_short, positions] = result;
```

---

## 交易模式枚举

### Python 版本
```python
trade_mode: str
# 取值: "fixed", "cash_all", "portfolio_pct", "fixed_cash"
```

### C++ 版本
```cpp
enum class TradeMode {
    FIXED,          // 固定仓位大小
    CASH_ALL,       // 全部现金买入
    PORTFOLIO_PCT,  // 组合百分比分配
    FIXED_CASH      // 固定金额交易
};
```

---

## 数据类型映射

| Python (NumPy) | C++ (Eigen) | 说明 |
|---------------|-------------|------|
| `np.float32` | `MatrixXf` / `VectorXf` | 单精度浮点 |
| `np.float64` | `MatrixXd` / `VectorXd` | 双精度浮点 |
| `np.int8` | `MatrixXi` | 整数（持仓信号） |
| `(n,)` 数组 | `VectorXf` | 一维向量 |
| `(n, m)` 数组 | `MatrixXf` | 二维矩阵 |

---

## 代码迁移示例

### Python 简化版 → C++

**Python**:
```python
def run_backtest_python(prices, position_matrix, initial_cash=1000000.0):
    n_timesteps = len(prices)
    n_weights = position_matrix.shape[1]
    
    cash_matrix = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    cash_matrix[0, :] = initial_cash
    
    for t in range(1, n_timesteps):
        price = prices[t]
        for w in range(n_weights):
            # ... 处理逻辑
    
    return portfolio_values, cash_matrix, quantity_matrix
```

**C++**:
```cpp
std::tuple<MatrixXf, MatrixXf, MatrixXf> 
run_backtest(const VectorXf& prices, 
             const MatrixXi& position_matrix,
             float initial_cash = 1000000.0f) {
    int n_timesteps = prices.size();
    int n_weights = position_matrix.cols();
    
    MatrixXf cash_matrix = MatrixXf::Zero(n_timesteps, n_weights);
    cash_matrix.row(0).setConstant(initial_cash);
    
    for (int t = 1; t < n_timesteps; ++t) {
        float price = prices(t);
        for (int w = 0; w < n_weights; ++w) {
            // ... 处理逻辑
        }
    }
    
    return {portfolio_values, cash_matrix, quantity_matrix};
}
```

---

## 版本选择建议

### 用于 C++ 开发

**推荐使用**: `core_engine.py` (简化版)

**原因**:
- ✅ 双重循环逻辑清晰，易于转换为 C++
- ✅ 变量名更简洁
- ✅ 代码结构与 C++ 循环一致

### 用于性能验证

**推荐使用**: `core_engine_vectorized.py` (向量化版)

**原因**:
- ✅ 完全复制原版逻辑
- ✅ 性能最优（NumPy 向量化）
- ✅ 用于验证 C++ 实现的正确性

---

## 测试对比

### 运行性能对比

```bash
cd test_cases
python benchmark.py --scale medium
```

**预期输出**:
```
=== 基准测试 2: 回测引擎 ===
Python 简化版耗时: 245.3 ms
Python 向量化版耗时: 156.8 ms
向量化加速: 1.56x

C++ 耗时: 8.2 ms
相比简化版加速: 29.9x
相比向量化版加速: 19.1x
```

### 正确性验证

```bash
cd reference_impl
python core_engine_vectorized.py
```

**预期输出**:
```
=== 性能对比 ===
简化版耗时: 245.32 ms
向量化版耗时: 156.78 ms
加速比: 1.56x

数值误差: 3.2e-7
✓ 两个版本结果一致
```

---

## 常见问题

### Q: 为什么有两个 Python 版本？

**A**: 
- **简化版**: 用于 C++ 开发，逻辑清晰
- **向量化版**: 用于性能基准，完全复制原版

### Q: C++ 应该参考哪个版本？

**A**: 参考**简化版** (`core_engine.py`)，它的循环结构更适合 C++

### Q: 如何验证 C++ 实现正确性？

**A**: 与**向量化版**对比，因为它是原版逻辑的精确复制

### Q: 变量名不一致怎么办？

**A**: 参考本文档的「变量名对应关系」表格，统一使用 C++ 推荐命名

---

## 更新日志

- 2025-10-21: 初始版本，添加命名规范和版本对比

