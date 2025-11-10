"""
测试不同load_data方法的性能
"""

import time
import os
import sys
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocess_data import (
    save_data_as_parquet_optimized,
    load_data_from_parquet_optimized,
    load_data_from_parquet_vectorized,
    load_data_from_parquet_ultra_fast,
    OUTPUT_DIR
)


def generate_time_str(index):
    """生成合法的交易时间字符串"""
    base_time = datetime.strptime("09:31:00", "%H:%M:%S")
    new_time = base_time + timedelta(minutes=index)
    return new_time.strftime("%H:%M:%S")


def generate_test_data(num_times, num_stocks):
    """生成测试数据"""
    test_data = {}
    for i in range(num_times):
        time_str = generate_time_str(i)
        test_data[time_str] = {}
        for j in range(num_stocks):
            stock_code = f"60{j:04d}"
            test_data[time_str][stock_code] = {
                'rolling1': {'mean': np.random.uniform(100, 10000), 'std': np.random.uniform(10, 500)},
                'rolling5': {'mean': np.random.uniform(500, 50000), 'std': np.random.uniform(50, 2500)},
                'rolling10': {'mean': np.random.uniform(1000, 100000), 'std': np.random.uniform(100, 5000)},
                'rolling30': {'mean': np.random.uniform(3000, 300000), 'std': np.random.uniform(300, 15000)},
                'rolling_full': {'mean': np.random.uniform(5000, 500000), 'std': np.random.uniform(500, 25000)},
            }
    return test_data


def benchmark_load_methods():
    """对比不同加载方法的性能"""
    print("\n" + "="*80)
    print("Parquet加载方法性能对比")
    print("="*80)
    
    # 测试配置
    test_configs = [
        (50, 500, "中规模"),
        (240, 1000, "大规模（1天）"),
    ]
    
    methods = [
        ("原优化版本", load_data_from_parquet_optimized),
        ("向量化版本", load_data_from_parquet_vectorized),
        ("超快版本", load_data_from_parquet_ultra_fast),
    ]
    
    for num_times, num_stocks, label in test_configs:
        print(f"\n{'='*80}")
        print(f"测试规模: {label} ({num_times}个时间点 × {num_stocks}只股票)")
        print(f"{'='*80}")
        
        # 生成测试数据
        print(f"📊 生成测试数据...")
        test_data = generate_test_data(num_times, num_stocks)
        
        # 保存为parquet
        test_file = os.path.join(OUTPUT_DIR, f"load_test_{label}.parquet")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        print(f"💾 保存测试文件...")
        save_data_as_parquet_optimized(test_data, test_file.replace('.parquet', '.json'))
        file_size = os.path.getsize(test_file) / (1024 * 1024)
        print(f"   文件大小: {file_size:.2f} MB")
        
        # 测试每种方法
        print(f"\n{'方法':<20} {'读取时间':<15} {'速度提升':<15}")
        print("-" * 80)
        
        baseline_time = None
        for method_name, method_func in methods:
            # 预热
            _ = method_func(test_file)
            
            # 正式测试（运行3次取平均）
            times = []
            for _ in range(3):
                start = time.time()
                result = method_func(test_file)
                elapsed = time.time() - start
                times.append(elapsed)
            
            avg_time = np.mean(times)
            
            if baseline_time is None:
                baseline_time = avg_time
                speedup = "基准"
            else:
                speedup = f"{baseline_time / avg_time:.1f}x 更快"
            
            print(f"{method_name:<20} {avg_time:<15.3f} {speedup:<15}")
        
        # 清理
        if os.path.exists(test_file):
            os.remove(test_file)
    
    print("\n" + "="*80)


if __name__ == "__main__":
    benchmark_load_methods()
