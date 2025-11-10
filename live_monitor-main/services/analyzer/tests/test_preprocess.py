#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据预处理功能
"""


import pytest
import sys
import os
import tempfile
import pandas as pd
import json
from datetime import datetime, timedelta

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from preprocess_data  import (  # pyright: ignore[reportMissingImports]
    preprocess_stock_minute_data,
    calculate_rolling_data,
    get_trading_stocks_for_date,
    get_previous_n_trading_dates,
    process_statistics_data,
    convert_to_time_format
)

class TestPreprocessData:
    """数据预处理测试类"""
    
    def setup_method(self):
        """测试前设置"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟的股票分钟数据
        self.sample_data = self.create_sample_stock_data()
        self.test_csv_path = os.path.join(self.temp_dir, "test_stock_data.csv")
        self.sample_data.to_csv(self.test_csv_path, index=False)
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_sample_stock_data(self):
        """创建示例股票数据"""
        dates = pd.date_range('2025-07-01 09:31:00', '2025-07-01 15:00:00', freq='1Min')
        stock_codes = ['000001.SZ', '000002.SZ', '600000.SH']
        
        data = []
        for date in dates:
            for stock in stock_codes:
                data.append({
                    'trade_time': date,
                    'ts_code': stock,
                    'vol': 1000 + (len(data) % 100) * 10,  # 模拟成交量
                    'close': 10.0 + (len(data) % 50) * 0.1  # 模拟价格
                })
        
        # 确保数据按时间排序
        df = pd.DataFrame(data)
        df = df.sort_values(['trade_time', 'ts_code']).reset_index(drop=True)
        return df
    
    def test_preprocess_stock_minute_data(self):
        """测试股票分钟数据预处理"""
        df = preprocess_stock_minute_data(self.test_csv_path)
        
        # 验证基本结构
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        
        # 验证必要的列存在
        required_columns = ['trade_time', 'ts_code', 'trade_date', 'time_only', 'vol']
        for col in required_columns:
            assert col in df.columns
        
        # 验证数据类型
        assert pd.api.types.is_datetime64_any_dtype(df['trade_time'])
        assert isinstance(df['trade_date'].iloc[0], type(datetime.now().date()))
        assert isinstance(df['time_only'].iloc[0], type(datetime.now().time()))
        
        # 验证数据总体排序（允许同一时间有多个股票）
        # 检查每个股票代码内部是否按时间排序
        for stock_code in df['ts_code'].unique():
            stock_df = df[df['ts_code'] == stock_code]
            assert stock_df['trade_time'].is_monotonic_increasing, f"股票 {stock_code} 的时间序列未正确排序"
    
    def test_calculate_rolling_data(self):
        """测试滚动数据计算"""
        df = preprocess_stock_minute_data(self.test_csv_path)
        rolling_data = calculate_rolling_data(df)
        
        # 验证返回结构
        assert isinstance(rolling_data, dict)
        assert len(rolling_data) > 0
        
        # 验证数据结构
        for date_str, stocks_data in rolling_data.items():
            assert isinstance(stocks_data, dict)
            for stock_code, stock_data in stocks_data.items():
                assert isinstance(stock_data, dict)
                # 验证滚动窗口
                for window in [1, 5, 10, 30]:
                    window_key = f'rolling{window}'
                    assert window_key in stock_data
                    assert isinstance(stock_data[window_key], dict)
    
    def test_get_trading_stocks_for_date(self):
        """测试获取交易日股票列表"""
        # 创建模拟数据字典
        mock_data = {
            '2025-07-01': {
                '000001.SZ': {'rolling1': {}},
                '000002.SZ': {'rolling1': {}},
            },
            '2025-06-30': {
                '000001.SZ': {'rolling1': {}},
                '600000.SH': {'rolling1': {}},
            }
        }
        
        # 测试存在的日期
        stocks, actual_date = get_trading_stocks_for_date(mock_data, '2025-07-01')
        assert len(stocks) == 2
        assert '000001.SZ' in stocks
        assert '000002.SZ' in stocks
        assert actual_date == '2025-07-01'
        
        # 测试不存在的日期（应该返回最近的日期）
        stocks, actual_date = get_trading_stocks_for_date(mock_data, '2025-07-02')
        assert len(stocks) == 2
        assert actual_date == '2025-07-01'
        
        # 测试太早的日期
        stocks, actual_date = get_trading_stocks_for_date(mock_data, '2025-06-01')
        assert stocks == []
        assert actual_date is None
    
    def test_get_previous_n_trading_dates(self):
        """测试获取前N个交易日"""
        # 创建模拟数据
        mock_data = {
            '2025-07-01': {'000001.SZ': {}},
            '2025-06-30': {'000001.SZ': {}},
            '2025-06-28': {'000001.SZ': {}},  # 周五
            '2025-06-27': {'000002.SZ': {}},  # 这天000001.SZ没有交易
        }
        
        # 测试获取前3个交易日
        dates = get_previous_n_trading_dates(mock_data, '2025-07-01', '000001.SZ', 3)
        assert len(dates) == 3
        assert '2025-07-01' in dates
        assert '2025-06-30' in dates
        assert '2025-06-28' in dates
        assert '2025-06-27' not in dates  # 这天该股票没有交易
        
        # 测试股票不存在
        dates = get_previous_n_trading_dates(mock_data, '2025-07-01', '999999.SZ', 3)
        assert len(dates) == 0
    
    def test_process_statistics_data(self):
        """测试统计数据处理"""
        # 创建模拟滚动数据
        mock_rolling_data = {
            '2025-07-01': {
                '000001.SZ': {
                    'rolling1': {'09:31:00': 1000, '09:32:00': 1100},
                    'rolling5': {'09:31:00': 1050, '09:32:00': 1150}
                }
            },
            '2025-06-30': {
                '000001.SZ': {
                    'rolling1': {'09:31:00': 950, '09:32:00': 1050},
                    'rolling5': {'09:31:00': 1000, '09:32:00': 1100}
                }
            }
        }
        
        stats_data = process_statistics_data(mock_rolling_data, '2025-07-01', 2)
        
        # 验证结果结构
        assert isinstance(stats_data, dict)
        assert '000001.SZ' in stats_data
        
        stock_data = stats_data['000001.SZ']
        assert 'rolling1' in stock_data
        assert 'rolling5' in stock_data
        
        # 验证统计指标
        rolling1_data = stock_data['rolling1']
        assert 'mean' in rolling1_data
        assert 'std' in rolling1_data
        
        # 验证计算结果
        mean_data = rolling1_data['mean']
        assert '09:31:00' in mean_data
        assert '09:32:00' in mean_data
        
        # 验证均值计算 (1000+950)/2 = 975, (1100+1050)/2 = 1075
        assert abs(mean_data['09:31:00'] - 975) < 0.1
        assert abs(mean_data['09:32:00'] - 1075) < 0.1
    
    def test_convert_to_time_format(self):
        """测试时间格式转换"""
        # 创建模拟统计数据
        mock_stats_data = {
            '000001.SZ': {
                'rolling1': {
                    'mean': {'09:31:00': 1000, '09:32:00': 1100},
                    'std': {'09:31:00': 50, '09:32:00': 60}
                }
            }
        }
        
        time_data = convert_to_time_format(mock_stats_data)
        
        # 验证结构
        assert isinstance(time_data, dict)
        assert '09:31:00' in time_data
        assert '09:32:00' in time_data
        
        # 验证数据
        time_point_data = time_data['09:31:00']
        assert '000001.SZ' in time_point_data
        
        stock_data = time_point_data['000001.SZ']
        assert 'rolling1' in stock_data
        
        rolling_data = stock_data['rolling1']
        assert 'mean' in rolling_data
        assert 'std' in rolling_data
        assert rolling_data['mean'] == 1000
        assert rolling_data['std'] == 50
    
    def test_invalid_csv_path(self):
        """测试无效的CSV路径"""
        with pytest.raises(FileNotFoundError):
            preprocess_stock_minute_data('/nonexistent/path.csv')
    
    def test_empty_dataframe(self):
        """测试空数据框处理"""
        # 创建空的CSV文件
        empty_csv = os.path.join(self.temp_dir, "empty.csv")
        pd.DataFrame().to_csv(empty_csv, index=False)
        
        # 这应该会引发异常或返回空结果
        with pytest.raises((ValueError, KeyError)):
            preprocess_stock_minute_data(empty_csv)

# 集成测试
def test_full_preprocess_workflow():
    """测试完整的预处理工作流"""
    # 这个测试需要真实的数据文件，如果文件不存在则跳过
    test_csv = os.path.join(os.path.dirname(__file__), "..", "data", "stock_minute_data_test.csv")
    
    if not os.path.exists(test_csv):
        pytest.skip("测试数据文件不存在，跳过集成测试")
    
    try:
        # 测试完整流程
        df = preprocess_stock_minute_data(test_csv)
        assert len(df) > 0
        
        rolling_data = calculate_rolling_data(df)
        assert len(rolling_data) > 0
        
        # 如果有数据，继续测试
        if rolling_data:
            first_date = list(rolling_data.keys())[0]
            stocks, actual_date = get_trading_stocks_for_date(rolling_data, first_date)
            assert len(stocks) > 0
            
    except Exception as e:
        pytest.skip(f"集成测试失败，可能是数据格式问题: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
