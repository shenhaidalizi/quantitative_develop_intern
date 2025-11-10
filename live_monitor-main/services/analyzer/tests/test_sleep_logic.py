#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试睡眠逻辑的脚本
使用pytest框架验证程序在非交易时间的睡眠功能
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, time
from unittest.mock import patch

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# 修正导入路径
from timely_data import get_time_status_and_sleep, format_time_duration

class TestSleepLogic:
    """睡眠逻辑测试类"""
    
    def test_format_time_duration(self):
        """测试时间格式化函数"""
        # 测试小于1小时
        hours, minutes, seconds = format_time_duration(3665)  # 1小时1分5秒
        assert hours == 1
        assert minutes == 1
        assert seconds == 5
        
        # 测试整小时
        hours, minutes, seconds = format_time_duration(7200)  # 2小时
        assert hours == 2
        assert minutes == 0
        assert seconds == 0
        
        # 测试小于1分钟
        hours, minutes, seconds = format_time_duration(45)  # 45秒
        assert hours == 0
        assert minutes == 0
        assert seconds == 45
    
    @patch('timely_data.datetime')
    def test_morning_wait_status(self, mock_datetime):
        """测试早上开盘前等待状态"""
        # 模拟当前时间为08:30:00
        mock_now = datetime(2024, 1, 15, 8, 30, 0)  # 周一
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        mock_datetime.strptime = datetime.strptime
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == 'wait'
        assert next_session == "早盘开盘"
        assert wait_seconds > 0
        # 应该等待1小时1分钟（到9:31）
        expected_wait = 61 * 60  # 61分钟
        assert abs(wait_seconds - expected_wait) < 60  # 允许1分钟误差
    
    @patch('timely_data.datetime')
    def test_lunch_wait_status(self, mock_datetime):
        """测试中午休市等待状态"""
        # 模拟当前时间为12:00:00
        mock_now = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        mock_datetime.strptime = datetime.strptime
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == 'wait'
        assert next_session == "午盘开盘"
        assert wait_seconds > 0
        # 应该等待1小时（到13:00）
        expected_wait = 60 * 60  # 1小时
        assert abs(wait_seconds - expected_wait) < 60
    
    @patch('timely_data.datetime')
    def test_trading_status(self, mock_datetime):
        """测试交易时间状态"""
        # 测试上午交易时间
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == 'trading'
        assert wait_seconds == 0
        assert next_session == "交易时间内"
        
        # 测试下午交易时间
        mock_now = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.now.return_value = mock_now
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == 'trading'
        assert wait_seconds == 0
    
    @patch('timely_data.datetime')
    def test_exit_status(self, mock_datetime):
        """测试收盘后退出状态"""
        # 模拟当前时间为16:00:00
        mock_now = datetime(2024, 1, 15, 16, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        mock_datetime.strptime = datetime.strptime
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == 'exit'
        assert next_session == "明日早盘开盘"
        assert wait_seconds > 0
        # 应该等待到明天9:31
        expected_wait = 17.5 * 60 * 60  # 大约17.5小时
        assert abs(wait_seconds - expected_wait) < 3600  # 允许1小时误差
    
    @pytest.mark.parametrize("hour,minute,expected_status", [
        (8, 30, 'wait'),      # 开盘前
        (9, 31, 'trading'),   # 开盘
        (10, 30, 'trading'),  # 交易中
        (11, 29, 'trading'),  # 上午最后交易时间
        (11, 31, 'wait'),     # 上午收盘后，等待下午开盘
        (12, 0, 'wait'),      # 中午休息
        (13, 0, 'trading'),   # 下午开盘
        (14, 30, 'trading'),  # 交易中
        (14, 59, 'trading'),  # 下午最后交易时间
        (15, 0, 'exit'),      # 收盘时间（退出）
        (16, 0, 'exit'),      # 收盘后
        (23, 0, 'exit'),      # 深夜
    ])
    @patch('timely_data.datetime')
    def test_various_time_status(self, mock_datetime, hour, minute, expected_status):
        """参数化测试不同时间的状态"""
        mock_now = datetime(2024, 1, 15, hour, minute, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        mock_datetime.strptime = datetime.strptime
        
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        assert status == expected_status
        
        if expected_status == 'trading':
            assert wait_seconds == 0
        else:
            assert wait_seconds > 0

def test_sleep_logic_integration():
    """集成测试睡眠逻辑"""
    # 这个测试使用真实时间，验证函数不会抛出异常
    try:
        status, wait_seconds, next_session, message = get_time_status_and_sleep()
        
        # 验证返回值类型
        assert isinstance(status, str)
        assert isinstance(wait_seconds, (int, float))
        assert isinstance(next_session, str)
        assert isinstance(message, str)
        
        # 验证状态值
        assert status in ['trading', 'wait', 'exit']
        
        # 验证等待时间
        assert wait_seconds >= 0
        
    except Exception as e:
        pytest.fail(f"睡眠逻辑函数抛出异常: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 