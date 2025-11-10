# C++ 接口定义规范

## 1. 总体要求

### 1.1 编程规范
- **C++ 标准**: C++17 或更高
- **命名风格**: Google C++ Style Guide
- **注释格式**: Doxygen
- **错误处理**: 异常 (throw std::exception)

### 1.2 依赖库
```cmake
# CMakeLists.txt
find_package(Eigen3 REQUIRED)
find_package(pybind11 REQUIRED)
find_package(OpenMP)

target_link_libraries(backtest_cpp 
    PRIVATE 
    Eigen3::Eigen 
    pybind11::module
    OpenMP::OpenMP_CXX
)
```

---

## 2. 核心接口定义

### 2.1 SignalProcessor (信号处理器)

#### C++ 头文件
```cpp
// include/signal_processor.h
#pragma once
#include <Eigen/Dense>
#include <tuple>

namespace backtest {

/**
 * @brief 信号组合处理器
 * 
 * 将多个信号按权重组合，生成持仓信号矩阵
 */
class SignalProcessor {
public:
    /**
     * @brief 处理信号矩阵，生成组合信号和持仓
     * 
     * @param signal_matrix 信号矩阵 (n_timesteps x n_signals)
     * @param weights_matrix 权重矩阵 (n_signals x n_weights)
     * @param threshold 信号阈值，默认 0.5
     * 
     * @return std::tuple<MatrixXf, MatrixXi, MatrixXi>
     *         - combined_signals: 组合信号 (n_timesteps x n_weights)
     *         - long_short_matrix: 多空信号 (n_timesteps x n_weights), 取值 {-1, 0, 1}
     *         - position_matrix: 持仓矩阵 (n_timesteps x n_weights), 取值 {-1, 0, 1}
     * 
     * @throws std::invalid_argument 如果矩阵维度不匹配
     */
    static std::tuple<Eigen::MatrixXf, Eigen::MatrixXi, Eigen::MatrixXi>
    process_signals(
        const Eigen::MatrixXf& signal_matrix,
        const Eigen::MatrixXf& weights_matrix,
        float threshold = 0.5f
    );
    
private:
    /**
     * @brief 应用阈值生成多空信号
     */
    static void apply_threshold(
        const Eigen::MatrixXf& combined,
        Eigen::MatrixXi& long_short,
        float threshold
    );
    
    /**
     * @brief 滞后一期生成持仓矩阵
     */
    static void lag_positions(
        const Eigen::MatrixXi& long_short,
        Eigen::MatrixXi& positions
    );
};

}  // namespace backtest
```

#### Python 接口
```python
import numpy as np
from backtest_cpp import signal_processor

# 函数签名
def process_signals(
    signal_matrix: np.ndarray,    # shape: (n_timesteps, n_signals), dtype: float32
    weights_matrix: np.ndarray,   # shape: (n_signals, n_weights), dtype: float32
    threshold: float = 0.5        # 信号阈值
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    处理信号矩阵
    
    Returns:
        combined_signals: (n_timesteps, n_weights) float32
        long_short_matrix: (n_timesteps, n_weights) int8
        position_matrix: (n_timesteps, n_weights) int8
    """
    pass

# 使用示例
signals = np.random.randn(1000, 10).astype(np.float32)
weights = np.random.randn(10, 100).astype(np.float32)
combined, long_short, positions = process_signals(signals, weights, threshold=0.5)
```

---

### 2.2 BacktestEngine (回测引擎)

#### C++ 头文件
```cpp
// include/backtest_engine.h
#pragma once
#include <Eigen/Dense>
#include <string>
#include <tuple>

namespace backtest {

/**
 * @brief 交易模式枚举
 */
enum class TradeMode {
    CASH_ALL,        // 全部现金买入
    PORTFOLIO_PCT,   // 组合百分比分配
    FIXED_CASH       // 固定金额交易
};

/**
 * @brief 回测配置
 */
struct BacktestConfig {
    float initial_cash = 1000000.0f;
    TradeMode trade_mode = TradeMode::PORTFOLIO_PCT;
    float max_allocation_pct = 0.5f;  // 仅 PORTFOLIO_PCT 模式使用
    float fixed_cash_amount = 100000.0f;  // 仅 FIXED_CASH 模式使用
};

/**
 * @brief 回测引擎
 */
class BacktestEngine {
public:
    /**
     * @brief 运行多权重回测
     * 
     * @param prices 价格序列 (n_timesteps,)
     * @param position_matrix 持仓信号矩阵 (n_timesteps x n_weights), 取值 {-1, 0, 1}
     * @param config 回测配置
     * 
     * @return std::tuple<MatrixXf, MatrixXf, MatrixXf>
     *         - portfolio_values: 组合价值 (n_timesteps x n_weights)
     *         - cash_matrix: 现金矩阵 (n_timesteps x n_weights)
     *         - quantity_matrix: 持仓数量 (n_timesteps x n_weights)
     * 
     * @throws std::invalid_argument 如果输入无效
     */
    static std::tuple<Eigen::MatrixXf, Eigen::MatrixXf, Eigen::MatrixXf>
    run_backtest(
        const Eigen::VectorXf& prices,
        const Eigen::MatrixXi& position_matrix,
        const BacktestConfig& config
    );
    
private:
    static void process_buy_signal(
        float price,
        float& cash,
        float& quantity,
        const BacktestConfig& config,
        float portfolio_value
    );
    
    static void process_sell_signal(
        float price,
        float& cash,
        float& quantity
    );
};

}  // namespace backtest
```

#### Python 接口
```python
from backtest_cpp import backtest_engine
import numpy as np

# 函数签名
def run_backtest(
    prices: np.ndarray,           # shape: (n_timesteps,), dtype: float32
    position_matrix: np.ndarray,  # shape: (n_timesteps, n_weights), dtype: int8
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct",  # "cash_all" / "portfolio_pct" / "fixed_cash"
    max_allocation_pct: float = 0.5,
    fixed_cash_amount: float = 100000.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    运行多权重回测
    
    Returns:
        portfolio_values: (n_timesteps, n_weights) float32
        cash_matrix: (n_timesteps, n_weights) float32
        quantity_matrix: (n_timesteps, n_weights) float32
    """
    pass

# 使用示例
prices = np.array([100, 101, 102, 101, 103], dtype=np.float32)
positions = np.array([[0, 0], [1, 0], [1, 0], [0, 0], [0, 0]], dtype=np.int8)
portfolio, cash, qty = run_backtest(
    prices, positions, 
    initial_cash=10000.0,
    trade_mode="cash_all"
)
```

---

### 2.3 MetricsCalculator (指标计算器)

#### C++ 头文件
```cpp
// include/metrics_calculator.h
#pragma once
#include <Eigen/Dense>

namespace backtest {

/**
 * @brief 性能指标计算器
 */
class MetricsCalculator {
public:
    /**
     * @brief 计算夏普比率
     * 
     * @param portfolio_values 组合价值矩阵 (n_timesteps x n_weights)
     * @param annualization_factor 年化因子，默认 252
     * 
     * @return VectorXf 夏普比率 (n_weights,)
     */
    static Eigen::VectorXf calculate_sharpe_ratio(
        const Eigen::MatrixXf& portfolio_values,
        float annualization_factor = 252.0f
    );
    
    /**
     * @brief 计算最大回撤
     * 
     * @param portfolio_values 组合价值矩阵 (n_timesteps x n_weights)
     * 
     * @return VectorXf 最大回撤 (n_weights,)
     */
    static Eigen::VectorXf calculate_max_drawdown(
        const Eigen::MatrixXf& portfolio_values
    );
    
    /**
     * @brief 计算收益率矩阵
     * 
     * @param portfolio_values 组合价值矩阵 (n_timesteps x n_weights)
     * 
     * @return MatrixXf 收益率矩阵 (n_timesteps-1 x n_weights)
     */
    static Eigen::MatrixXf calculate_returns(
        const Eigen::MatrixXf& portfolio_values
    );
    
    /**
     * @brief 计算总收益率
     * 
     * @param portfolio_values 组合价值矩阵 (n_timesteps x n_weights)
     * 
     * @return VectorXf 总收益率 (n_weights,)
     */
    static Eigen::VectorXf calculate_total_return(
        const Eigen::MatrixXf& portfolio_values
    );
};

}  // namespace backtest
```

#### Python 接口
```python
from backtest_cpp import metrics_calculator
import numpy as np

def calculate_sharpe_ratio(
    portfolio_values: np.ndarray,  # (n_timesteps, n_weights), float32
    annualization_factor: float = 252.0
) -> np.ndarray:  # (n_weights,), float32
    """计算夏普比率"""
    pass

def calculate_max_drawdown(
    portfolio_values: np.ndarray  # (n_timesteps, n_weights), float32
) -> np.ndarray:  # (n_weights,), float32
    """计算最大回撤"""
    pass

def calculate_returns(
    portfolio_values: np.ndarray  # (n_timesteps, n_weights), float32
) -> np.ndarray:  # (n_timesteps-1, n_weights), float32
    """计算收益率矩阵"""
    pass

# 使用示例
portfolio_values = np.random.rand(1000, 100).astype(np.float32) * 1000000
sharpe = calculate_sharpe_ratio(portfolio_values)
max_dd = calculate_max_drawdown(portfolio_values)
```

---

### 2.4 OptimizerKernel (优化器核心)

#### C++ 头文件
```cpp
// include/optimizer_kernel.h
#pragma once
#include <Eigen/Dense>
#include "backtest_engine.h"

namespace backtest {

/**
 * @brief 优化器核心，整合信号处理和回测
 */
class OptimizerKernel {
public:
    /**
     * @brief 批量评估权重组合
     * 
     * @param weights_batch 权重批次 (n_signals x n_candidates)
     * @param signal_matrix 信号矩阵 (n_timesteps x n_signals)
     * @param prices 价格序列 (n_timesteps,)
     * @param threshold 信号阈值
     * @param config 回测配置
     * 
     * @return VectorXf 夏普比率 (n_candidates,)
     * 
     * @note 此函数整合了信号处理、回测和指标计算，避免中间结果传递
     */
    static Eigen::VectorXf evaluate_weights_batch(
        const Eigen::MatrixXf& weights_batch,
        const Eigen::MatrixXf& signal_matrix,
        const Eigen::VectorXf& prices,
        float threshold,
        const BacktestConfig& config
    );
    
    /**
     * @brief 单个权重组合评估（便捷接口）
     */
    static float evaluate_single_weight(
        const Eigen::VectorXf& weights,
        const Eigen::MatrixXf& signal_matrix,
        const Eigen::VectorXf& prices,
        float threshold,
        const BacktestConfig& config
    );
};

}  // namespace backtest
```

#### Python 接口
```python
from backtest_cpp import optimizer_kernel
import numpy as np

def evaluate_weights_batch(
    weights_batch: np.ndarray,    # (n_signals, n_candidates), float32
    signal_matrix: np.ndarray,    # (n_timesteps, n_signals), float32
    prices: np.ndarray,           # (n_timesteps,), float32
    threshold: float = 0.5,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct",
    max_allocation_pct: float = 0.5,
    fixed_cash_amount: float = 100000.0
) -> np.ndarray:  # (n_candidates,), float32
    """
    批量评估权重组合，返回每个组合的夏普比率
    
    此函数是性能优化的关键，用于优化算法中的批量评估
    """
    pass

# 使用示例
signals = np.random.randn(1000, 10).astype(np.float32)
prices = np.cumsum(np.random.randn(1000)).astype(np.float32) + 1000
weights_batch = np.random.randn(10, 10000).astype(np.float32)

scores = evaluate_weights_batch(
    weights_batch, signals, prices,
    threshold=0.5,
    trade_mode="cash_all"
)

best_idx = np.argmax(scores)
best_weights = weights_batch[:, best_idx]
```

---

## 3. Pybind11 绑定实现

### 3.1 模块定义
```cpp
// src/bindings.cpp
#include <pybind11/pybind11.h>
#include <pybind11/eigen.h>
#include <pybind11/stl.h>

#include "signal_processor.h"
#include "backtest_engine.h"
#include "metrics_calculator.h"
#include "optimizer_kernel.h"

namespace py = pybind11;
using namespace backtest;

PYBIND11_MODULE(backtest_cpp, m) {
    m.doc() = "C++ 加速的回测引擎模块";
    
    // SignalProcessor
    m.def("process_signals", 
        [](const Eigen::MatrixXf& signals, 
           const Eigen::MatrixXf& weights,
           float threshold) {
            return SignalProcessor::process_signals(signals, weights, threshold);
        },
        py::arg("signal_matrix"),
        py::arg("weights_matrix"),
        py::arg("threshold") = 0.5f,
        "处理信号矩阵，生成组合信号和持仓"
    );
    
    // BacktestEngine
    m.def("run_backtest",
        [](const Eigen::VectorXf& prices,
           const Eigen::MatrixXi& positions,
           float initial_cash,
           const std::string& trade_mode_str,
           float max_allocation_pct,
           float fixed_cash_amount) {
            
            BacktestConfig config;
            config.initial_cash = initial_cash;
            config.max_allocation_pct = max_allocation_pct;
            config.fixed_cash_amount = fixed_cash_amount;
            
            // 字符串转枚举
            if (trade_mode_str == "cash_all") {
                config.trade_mode = TradeMode::CASH_ALL;
            } else if (trade_mode_str == "portfolio_pct") {
                config.trade_mode = TradeMode::PORTFOLIO_PCT;
            } else if (trade_mode_str == "fixed_cash") {
                config.trade_mode = TradeMode::FIXED_CASH;
            } else {
                throw std::invalid_argument("不支持的交易模式: " + trade_mode_str);
            }
            
            return BacktestEngine::run_backtest(prices, positions, config);
        },
        py::arg("prices"),
        py::arg("position_matrix"),
        py::arg("initial_cash") = 1000000.0f,
        py::arg("trade_mode") = "portfolio_pct",
        py::arg("max_allocation_pct") = 0.5f,
        py::arg("fixed_cash_amount") = 100000.0f,
        "运行多权重回测"
    );
    
    // MetricsCalculator
    m.def("calculate_sharpe_ratio",
        &MetricsCalculator::calculate_sharpe_ratio,
        py::arg("portfolio_values"),
        py::arg("annualization_factor") = 252.0f,
        "计算夏普比率"
    );
    
    m.def("calculate_max_drawdown",
        &MetricsCalculator::calculate_max_drawdown,
        py::arg("portfolio_values"),
        "计算最大回撤"
    );
    
    // OptimizerKernel
    m.def("evaluate_weights_batch",
        [](const Eigen::MatrixXf& weights_batch,
           const Eigen::MatrixXf& signal_matrix,
           const Eigen::VectorXf& prices,
           float threshold,
           float initial_cash,
           const std::string& trade_mode_str,
           float max_allocation_pct,
           float fixed_cash_amount) {
            
            BacktestConfig config;
            config.initial_cash = initial_cash;
            config.max_allocation_pct = max_allocation_pct;
            config.fixed_cash_amount = fixed_cash_amount;
            
            if (trade_mode_str == "cash_all") {
                config.trade_mode = TradeMode::CASH_ALL;
            } else if (trade_mode_str == "portfolio_pct") {
                config.trade_mode = TradeMode::PORTFOLIO_PCT;
            } else if (trade_mode_str == "fixed_cash") {
                config.trade_mode = TradeMode::FIXED_CASH;
            }
            
            return OptimizerKernel::evaluate_weights_batch(
                weights_batch, signal_matrix, prices, threshold, config
            );
        },
        py::arg("weights_batch"),
        py::arg("signal_matrix"),
        py::arg("prices"),
        py::arg("threshold") = 0.5f,
        py::arg("initial_cash") = 1000000.0f,
        py::arg("trade_mode") = "portfolio_pct",
        py::arg("max_allocation_pct") = 0.5f,
        py::arg("fixed_cash_amount") = 100000.0f,
        "批量评估权重组合"
    );
}
```

---

## 4. 编译配置

### 4.1 CMakeLists.txt
```cmake
cmake_minimum_required(VERSION 3.15)
project(backtest_cpp VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 优化选项
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")

# 查找依赖
find_package(Eigen3 3.3 REQUIRED NO_MODULE)
find_package(pybind11 REQUIRED)
find_package(OpenMP)

# 源文件
set(SOURCES
    src/signal_processor.cpp
    src/backtest_engine.cpp
    src/metrics_calculator.cpp
    src/optimizer_kernel.cpp
    src/bindings.cpp
)

# 创建 Python 模块
pybind11_add_module(backtest_cpp ${SOURCES})

target_include_directories(backtest_cpp 
    PRIVATE 
    ${CMAKE_SOURCE_DIR}/include
)

target_link_libraries(backtest_cpp 
    PRIVATE 
    Eigen3::Eigen
)

if(OpenMP_CXX_FOUND)
    target_link_libraries(backtest_cpp PRIVATE OpenMP::OpenMP_CXX)
endif()

# 安装
install(TARGETS backtest_cpp DESTINATION .)
```

### 4.2 setup.py
```python
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import os

ext_modules = [
    Pybind11Extension(
        "backtest_cpp",
        ["src/signal_processor.cpp",
         "src/backtest_engine.cpp",
         "src/metrics_calculator.cpp",
         "src/optimizer_kernel.cpp",
         "src/bindings.cpp"],
        include_dirs=["include"],
        extra_compile_args=["-O3", "-march=native", "-fopenmp"],
        extra_link_args=["-fopenmp"],
    ),
]

setup(
    name="backtest_cpp",
    version="1.0.0",
    author="Your Name",
    description="C++ accelerated backtest engine",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
)
```

---

## 5. 使用示例

### 5.1 完整流程
```python
import numpy as np
from backtest_cpp import (
    process_signals,
    run_backtest,
    calculate_sharpe_ratio,
    evaluate_weights_batch
)

# 1. 准备数据
n_timesteps = 1000
n_signals = 10
n_weights = 100

signals = np.random.randn(n_timesteps, n_signals).astype(np.float32)
weights = np.random.randn(n_signals, n_weights).astype(np.float32)
prices = (np.cumsum(np.random.randn(n_timesteps)) + 1000).astype(np.float32)

# 2. 信号处理
combined, long_short, positions = process_signals(
    signals, weights, threshold=0.5
)

# 3. 回测
portfolio_values, cash, quantities = run_backtest(
    prices, positions,
    initial_cash=1000000.0,
    trade_mode="portfolio_pct"
)

# 4. 计算指标
sharpe = calculate_sharpe_ratio(portfolio_values)
print(f"最佳夏普比率: {sharpe.max():.4f}")

# 5. 优化场景：批量评估
weights_batch = np.random.randn(n_signals, 10000).astype(np.float32)
scores = evaluate_weights_batch(
    weights_batch, signals, prices, threshold=0.5
)
best_idx = np.argmax(scores)
print(f"最佳权重索引: {best_idx}, 得分: {scores[best_idx]:.4f}")
```

---

## 6. 接口测试要求

每个接口必须通过以下测试：

### 6.1 正确性测试
```python
def test_numerical_accuracy():
    """与 Python 参考实现对比，误差 < 1e-6"""
    # ... 测试代码
    assert np.allclose(cpp_result, python_result, atol=1e-6)
```

### 6.2 边界测试
```python
def test_edge_cases():
    """测试空数组、单元素数组、异常输入"""
    with pytest.raises(ValueError):
        process_signals(np.array([]), np.array([]))
```

### 6.3 性能测试
```python
def test_performance():
    """性能至少 10x Python"""
    assert cpp_time < python_time / 10
```

