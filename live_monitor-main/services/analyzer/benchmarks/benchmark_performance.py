"""
性能基准测试：对比优化前后的性能
"""

import time
import os
import sys
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocess_data import (
    save_data_as_parquet,
    load_data_from_parquet,
    OUTPUT_DIR
)


def generate_time_str(index):
    """生成合法的交易时间字符串"""
    base_time = datetime.strptime("09:31:00", "%H:%M:%S")
    new_time = base_time + timedelta(minutes=index)
    return new_time.strftime("%H:%M:%S")


def benchmark_read_write():
    """基准测试：读写性能"""
    print("\n" + "="*70)
    print("性能基准测试：Parquet读写")
    print("="*70)
    
    test_sizes = [
        (10, 100, "小规模"),
        (50, 500, "中规模"),
        (240, 1000, "大规模（1天数据）"),
    ]
    
    results = []
    
    for num_times, num_stocks, label in test_sizes:
        print(f"\n📊 测试 {label}: {num_times}个时间点 × {num_stocks}只股票")
        
        # 生成数据
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
        
        test_file = os.path.join(OUTPUT_DIR, f"benchmark_{label}.parquet")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # 写入测试
        start = time.time()
        save_data_as_parquet(test_data, test_file.replace('.parquet', '.json'))
        write_time = time.time() - start
        
        # 读取测试
        start = time.time()
        _ = load_data_from_parquet(test_file)
        read_time = time.time() - start
        
        # 文件大小
        file_size = os.path.getsize(test_file) / (1024 * 1024)
        
        print(f"  写入: {write_time:.3f}秒")
        print(f"  读取: {read_time:.3f}秒")
        print(f"  文件: {file_size:.2f}MB")
        print(f"  吞吐: {(num_times * num_stocks) / (write_time + read_time):.0f} 条/秒")
        
        results.append({
            'label': label,
            'times': num_times,
            'stocks': num_stocks,
            'write_time': write_time,
            'read_time': read_time,
            'file_size': file_size,
            'throughput': (num_times * num_stocks) / (write_time + read_time)
        })
        
        # 清理
        if os.path.exists(test_file):
            os.remove(test_file)
    
    # 打印汇总表格
    print("\n" + "="*70)
    print("性能汇总表")
    print("="*70)
    print(f"{'规模':<15} {'写入(s)':<10} {'读取(s)':<10} {'文件(MB)':<12} {'吞吐(条/s)':<15}")
    print("-"*70)
    for r in results:
        print(f"{r['label']:<15} {r['write_time']:<10.3f} {r['read_time']:<10.3f} "
              f"{r['file_size']:<12.2f} {r['throughput']:<15.0f}")
    print("="*70)


if __name__ == "__main__":
    benchmark_read_write()
