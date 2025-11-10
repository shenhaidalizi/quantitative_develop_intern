"""
单元测试运行器

验证 C++ 实现与 Python 参考实现的一致性
"""
import numpy as np
import sys
import os
import argparse

# 添加参考实现到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reference_impl import (
    process_signals_python,
    run_backtest_python,
    calculate_sharpe_ratio_python,
    evaluate_weights_batch_python
)


class TestRunner:
    """测试运行器"""
    
    def __init__(self, data_dir='.', tolerance=1e-5):
        self.data_dir = data_dir
        self.tolerance = tolerance
        self.test_results = []
        
        # 尝试导入 C++ 模块
        try:
            import backtest_cpp
            self.cpp_module = backtest_cpp
            self.cpp_available = True
            print("✓ C++ 模块已加载")
        except ImportError:
            self.cpp_module = None
            self.cpp_available = False
            print("⚠ C++ 模块未找到，仅运行 Python 测试")
    
    def load_test_data(self):
        """加载测试数据"""
        print("\n加载测试数据...")
        
        try:
            # 加载数据
            import pandas as pd
            df = pd.read_parquet(os.path.join(self.data_dir, 'sample_data.parquet'))
            prices = df['close'].values.astype(np.float32)
            
            signals = np.load(os.path.join(self.data_dir, 'sample_signals.npy'))
            weights = np.load(os.path.join(self.data_dir, 'sample_weights.npy'))
            expected = np.load(os.path.join(self.data_dir, 'expected_output.npz'))
            
            print(f"  价格序列: {prices.shape}")
            print(f"  信号矩阵: {signals.shape}")
            print(f"  权重矩阵: {weights.shape}")
            
            return prices, signals, weights, expected
        
        except FileNotFoundError as e:
            print(f"✗ 测试数据未找到: {e}")
            print("  请先运行: python generate_test_data.py")
            sys.exit(1)
    
    def test_signal_processing(self, signals, weights, expected, threshold=0.5):
        """测试信号处理"""
        print("\n" + "="*60)
        print("测试 1: 信号处理")
        print("="*60)
        
        # Python 实现
        py_combined, py_long_short, py_positions = process_signals_python(
            signals, weights, threshold
        )
        
        print(f"Python 实现:")
        print(f"  组合信号: {py_combined.shape}")
        print(f"  多空信号: {py_long_short.shape}, 唯一值: {np.unique(py_long_short)}")
        print(f"  持仓矩阵: {py_positions.shape}, 唯一值: {np.unique(py_positions)}")
        
        if not self.cpp_available:
            return
        
        # C++ 实现
        cpp_combined, cpp_long_short, cpp_positions = self.cpp_module.process_signals(
            signals, weights, threshold
        )
        
        print(f"\nC++ 实现:")
        print(f"  组合信号: {cpp_combined.shape}")
        print(f"  多空信号: {cpp_long_short.shape}")
        print(f"  持仓矩阵: {cpp_positions.shape}")
        
        # 对比
        error_combined = np.abs(py_combined - cpp_combined).max()
        error_long_short = np.abs(py_long_short - cpp_long_short).max()
        error_positions = np.abs(py_positions - cpp_positions).max()
        
        print(f"\n误差:")
        print(f"  组合信号: {error_combined:.2e}")
        print(f"  多空信号: {error_long_short:.2e}")
        print(f"  持仓矩阵: {error_positions:.2e}")
        
        # 验证
        passed = (
            error_combined < self.tolerance and
            error_long_short == 0 and
            error_positions == 0
        )
        
        if passed:
            print("\n✓ 信号处理测试通过")
        else:
            print(f"\n✗ 信号处理测试失败 (阈值: {self.tolerance})")
        
        self.test_results.append(('signal_processing', passed, error_combined))
        
        return cpp_combined, cpp_long_short, cpp_positions
    
    def test_backtest_engine(self, prices, positions, expected):
        """测试回测引擎"""
        print("\n" + "="*60)
        print("测试 2: 回测引擎")
        print("="*60)
        
        initial_cash = 1000000.0
        trade_mode = "portfolio_pct"
        
        # Python 实现
        py_portfolio, py_cash, py_qty = run_backtest_python(
            prices, positions, initial_cash, trade_mode
        )
        
        print(f"Python 实现:")
        print(f"  组合价值: {py_portfolio.shape}")
        print(f"  现金矩阵: {py_cash.shape}")
        print(f"  持仓数量: {py_qty.shape}")
        print(f"  最终价值: min={py_portfolio[-1].min():.2f}, max={py_portfolio[-1].max():.2f}")
        
        if not self.cpp_available:
            return
        
        # C++ 实现
        cpp_portfolio, cpp_cash, cpp_qty = self.cpp_module.run_backtest(
            prices, positions, initial_cash, trade_mode
        )
        
        print(f"\nC++ 实现:")
        print(f"  组合价值: {cpp_portfolio.shape}")
        print(f"  现金矩阵: {cpp_cash.shape}")
        print(f"  持仓数量: {cpp_qty.shape}")
        
        # 对比
        error_portfolio = np.abs(py_portfolio - cpp_portfolio).max()
        error_cash = np.abs(py_cash - cpp_cash).max()
        error_qty = np.abs(py_qty - cpp_qty).max()
        
        print(f"\n误差:")
        print(f"  组合价值: {error_portfolio:.2e}")
        print(f"  现金矩阵: {error_cash:.2e}")
        print(f"  持仓数量: {error_qty:.2e}")
        
        # 验证
        passed = (
            error_portfolio < self.tolerance * 10 and  # 回测累积误差略大
            error_cash < self.tolerance * 10 and
            error_qty < self.tolerance
        )
        
        if passed:
            print("\n✓ 回测引擎测试通过")
        else:
            print(f"\n✗ 回测引擎测试失败 (阈值: {self.tolerance * 10})")
        
        self.test_results.append(('backtest_engine', passed, error_portfolio))
        
        return cpp_portfolio
    
    def test_metrics_calculation(self, portfolio_values):
        """测试指标计算"""
        print("\n" + "="*60)
        print("测试 3: 指标计算")
        print("="*60)
        
        # Python 实现
        py_sharpe = calculate_sharpe_ratio_python(portfolio_values)
        
        print(f"Python 实现:")
        print(f"  夏普比率: min={py_sharpe.min():.4f}, max={py_sharpe.max():.4f}, mean={py_sharpe.mean():.4f}")
        
        if not self.cpp_available:
            return
        
        # C++ 实现
        cpp_sharpe = self.cpp_module.calculate_sharpe_ratio(portfolio_values)
        
        print(f"\nC++ 实现:")
        print(f"  夏普比率: min={cpp_sharpe.min():.4f}, max={cpp_sharpe.max():.4f}, mean={cpp_sharpe.mean():.4f}")
        
        # 对比
        error_sharpe = np.abs(py_sharpe - cpp_sharpe).max()
        
        print(f"\n误差:")
        print(f"  夏普比率: {error_sharpe:.2e}")
        
        # 验证
        passed = error_sharpe < self.tolerance * 100  # 夏普比率计算涉及标准差，误差略大
        
        if passed:
            print("\n✓ 指标计算测试通过")
        else:
            print(f"\n✗ 指标计算测试失败 (阈值: {self.tolerance * 100})")
        
        self.test_results.append(('metrics_calculation', passed, error_sharpe))
    
    def test_optimizer_kernel(self, signals, weights, prices):
        """测试优化器核心（端到端）"""
        print("\n" + "="*60)
        print("测试 4: 优化器核心（端到端）")
        print("="*60)
        
        threshold = 0.5
        initial_cash = 1000000.0
        
        # Python 实现
        py_scores = evaluate_weights_batch_python(
            weights, signals, prices, threshold, initial_cash
        )
        
        print(f"Python 实现:")
        print(f"  得分: min={py_scores.min():.4f}, max={py_scores.max():.4f}, mean={py_scores.mean():.4f}")
        
        if not self.cpp_available:
            return
        
        # C++ 实现
        cpp_scores = self.cpp_module.evaluate_weights_batch(
            weights, signals, prices, threshold, initial_cash
        )
        
        print(f"\nC++ 实现:")
        print(f"  得分: min={cpp_scores.min():.4f}, max={cpp_scores.max():.4f}, mean={cpp_scores.mean():.4f}")
        
        # 对比
        error_scores = np.abs(py_scores - cpp_scores).max()
        
        print(f"\n误差:")
        print(f"  得分: {error_scores:.2e}")
        
        # 验证
        passed = error_scores < self.tolerance * 1000  # 端到端误差最大
        
        if passed:
            print("\n✓ 优化器核心测试通过")
        else:
            print(f"\n✗ 优化器核心测试失败 (阈值: {self.tolerance * 1000})")
        
        self.test_results.append(('optimizer_kernel', passed, error_scores))
    
    def run_all_tests(self):
        """运行所有测试"""
        print("="*60)
        print("回测引擎 C++ 实现 - 单元测试")
        print("="*60)
        
        # 加载数据
        prices, signals, weights, expected = self.load_test_data()
        
        # 测试 1: 信号处理
        cpp_combined, cpp_long_short, cpp_positions = self.test_signal_processing(
            signals, weights, expected
        )
        
        # 测试 2: 回测引擎
        if self.cpp_available:
            cpp_portfolio = self.test_backtest_engine(prices, cpp_positions, expected)
        else:
            _, _, py_positions = process_signals_python(signals, weights, 0.5)
            py_portfolio, _, _ = run_backtest_python(prices, py_positions, 1000000.0)
            cpp_portfolio = py_portfolio
        
        # 测试 3: 指标计算
        self.test_metrics_calculation(cpp_portfolio)
        
        # 测试 4: 优化器核心
        self.test_optimizer_kernel(signals, weights[:, :10], prices)  # 使用子集加速
        
        # 总结
        self.print_summary()
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        if not self.cpp_available:
            print("⚠ C++ 模块未安装，无法进行对比测试")
            return
        
        passed_count = sum(1 for _, passed, _ in self.test_results if passed)
        total_count = len(self.test_results)
        
        for test_name, passed, error in self.test_results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{test_name:25s} {status:10s} (误差: {error:.2e})")
        
        print(f"\n通过率: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")
        
        if passed_count == total_count:
            print("\n🎉 所有测试通过！")
            return 0
        else:
            print(f"\n⚠ {total_count - passed_count} 个测试失败")
            return 1


def main():
    parser = argparse.ArgumentParser(description='运行单元测试')
    parser.add_argument('--data-dir', type=str, default='.', help='测试数据目录')
    parser.add_argument('--tolerance', type=float, default=1e-5, help='误差容忍度')
    parser.add_argument('--test', type=str, default='all', 
                        choices=['all', 'signal', 'backtest', 'metrics', 'optimizer'],
                        help='指定测试')
    
    args = parser.parse_args()
    
    runner = TestRunner(data_dir=args.data_dir, tolerance=args.tolerance)
    
    if args.test == 'all':
        exit_code = runner.run_all_tests()
    else:
        # 运行特定测试
        prices, signals, weights, expected = runner.load_test_data()
        
        if args.test == 'signal':
            runner.test_signal_processing(signals, weights, expected)
        elif args.test == 'backtest':
            _, _, positions = process_signals_python(signals, weights, 0.5)
            runner.test_backtest_engine(prices, positions, expected)
        elif args.test == 'metrics':
            _, _, positions = process_signals_python(signals, weights, 0.5)
            portfolio, _, _ = run_backtest_python(prices, positions, 1000000.0)
            runner.test_metrics_calculation(portfolio)
        elif args.test == 'optimizer':
            runner.test_optimizer_kernel(signals, weights[:, :10], prices)
        
        runner.print_summary()
        exit_code = 0
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

