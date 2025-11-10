#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股交易时间映射测试脚本
使用pytest框架测试时间映射功能
"""

import pytest
import sys
import os

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# 修正导入路径
from timely_data import (
    create_trading_time_map, 
    time_to_trading_index, 
    trading_index_to_time,
    get_previous_trading_time,
    is_trading_time,
    print_trading_map_info
)

class TestTradingTimeMap:
    """交易时间映射测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.time_to_index, self.index_to_time = create_trading_time_map()
    
    def test_create_trading_time_map(self):
        """测试创建交易时间映射"""
        # 验证映射是否创建成功
        assert len(self.time_to_index) > 0
        assert len(self.index_to_time) > 0
        assert len(self.time_to_index) == len(self.index_to_time)
        
        # 验证交易时间长度（实际是239分钟：9:31-11:29 + 13:00-14:59）
        expected_total_minutes = 239  # 119分钟（上午）+ 120分钟（下午）
        assert len(self.time_to_index) == expected_total_minutes
    
    def test_trading_time_boundaries(self):
        """测试交易时间边界"""
        # 测试开盘时间
        assert is_trading_time("09:31:00") == True
        assert is_trading_time("09:30:00") == False
        
        # 测试上午最后交易时间（11:29，不包括11:30）
        assert is_trading_time("11:29:00") == True
        assert is_trading_time("11:30:00") == False
        
        # 测试下午开盘
        assert is_trading_time("13:00:00") == True
        assert is_trading_time("12:59:00") == False
        
        # 测试下午最后交易时间（14:59，不包括15:00）
        assert is_trading_time("14:59:00") == True
        assert is_trading_time("15:00:00") == False
    
    @pytest.mark.parametrize("time_str,expected", [
        ("09:31:00", True),   # 开盘
        ("10:30:00", True),   # 交易中
        ("11:29:00", True),   # 上午最后交易时间
        ("11:30:00", False),  # 上午收盘（不包括）
        ("13:00:00", True),   # 下午开盘
        ("14:30:00", True),   # 交易中
        ("14:59:00", True),   # 下午最后交易时间
        ("15:00:00", False),  # 收盘（不包括）
        ("09:29:00", False),  # 非交易时间
        ("12:00:00", False),  # 中午休息
        ("15:01:00", False),  # 收盘后
        ("08:00:00", False),  # 开盘前
    ])
    def test_is_trading_time(self, time_str, expected):
        """参数化测试交易时间判断"""
        assert is_trading_time(time_str) == expected
    
    def test_time_index_conversion(self):
        """测试时间和索引的相互转换"""
        # 测试有效交易时间
        valid_times = ["09:31:00", "11:29:00", "13:00:00", "14:59:00"]
        
        for time_str in valid_times:
            index = time_to_trading_index(time_str)
            assert index is not None
            assert isinstance(index, int)
            assert index >= 0
            
            # 反向转换
            converted_time = trading_index_to_time(index)
            assert converted_time == time_str
    
    def test_invalid_time_conversion(self):
        """测试无效时间转换"""
        invalid_times = ["09:30:00", "11:30:00", "12:00:00", "15:00:00", "08:00:00"]
        
        for time_str in invalid_times:
            index = time_to_trading_index(time_str)
            assert index is None
    
    def test_previous_trading_time(self):
        """测试获取历史交易时间"""
        # 测试正常情况
        current_time = "10:00:00"
        prev_time_1min = get_previous_trading_time(current_time, 1)
        prev_time_5min = get_previous_trading_time(current_time, 5)
        
        assert prev_time_1min == "09:59:00"
        assert prev_time_5min == "09:55:00"
        
        # 测试边界情况（开盘后几分钟）
        current_time = "09:33:00"
        prev_time_5min = get_previous_trading_time(current_time, 5)
        assert prev_time_5min is not None
        
        # 测试无效时间
        invalid_time = "12:00:00"
        prev_time = get_previous_trading_time(invalid_time, 1)
        assert prev_time is None
    
    def test_index_boundaries(self):
        """测试索引边界"""
        # 测试第一个索引
        first_time = trading_index_to_time(0)
        assert first_time == "09:31:00"
        
        # 测试最后一个索引（14:59而不是15:00）
        total_minutes = len(self.index_to_time)
        last_time = trading_index_to_time(total_minutes - 1)
        assert last_time == "14:59:00"
        
        # 测试超出范围的索引
        invalid_time = trading_index_to_time(total_minutes)
        assert invalid_time is None
        
        invalid_time = trading_index_to_time(-1)
        assert invalid_time is None

def test_trading_map_info(capsys):
    """测试交易映射信息打印"""
    print_trading_map_info()
    captured = capsys.readouterr()
    assert "交易时间映射创建完成" in captured.out
    assert "239" in captured.out  # 应该有239分钟
    assert "09:31:00" in captured.out
    assert "14:59:00" in captured.out

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 