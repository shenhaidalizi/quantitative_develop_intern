#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础功能测试 - 确保核心模块可以正常导入和运行
"""

import pytest
import sys
import os

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

class TestBasicImports:
    """测试基本导入功能"""
    
    def test_import_timely_data(self):
        """测试导入timely_data模块"""
        try:
            import timely_data
            assert hasattr(timely_data, 'get_time_status_and_sleep')
            assert hasattr(timely_data, 'time_to_trading_index')
            assert hasattr(timely_data, 'manage_result_files')
        except ImportError as e:
            pytest.fail(f"无法导入timely_data模块: {e}")
    
    def test_import_preprocess_data(self):
        """测试导入preprocess_data模块"""
        try:
            import preprocess_data
            assert hasattr(preprocess_data, 'preprocess_stock_minute_data')
            assert hasattr(preprocess_data, 'main')
        except ImportError as e:
            pytest.fail(f"无法导入preprocess_data模块: {e}")
    
    def test_project_structure(self):
        """测试项目结构"""
        project_root = parent_dir
        
        # 检查重要文件是否存在
        important_files = [
            'timely_data.py',
            'preprocess_data.py',
            'README.md'
        ]
        
        for filename in important_files:
            file_path = os.path.join(project_root, filename)
            assert os.path.exists(file_path), f"重要文件 {filename} 不存在"
    
    def test_data_directories(self):
        """测试数据目录结构"""
        project_root = parent_dir
        
        # 检查数据目录
        data_dirs = ['data', 'statistic_data', 'test_function']
        
        for dirname in data_dirs:
            dir_path = os.path.join(project_root, dirname)
            if dirname != 'statistic_data':  # statistic_data可能不存在
                assert os.path.exists(dir_path), f"目录 {dirname} 不存在"

class TestBasicFunctionality:
    """测试基本功能"""
    
    def test_trading_time_map_creation(self):
        """测试交易时间映射创建"""
        from timely_data import create_trading_time_map
        
        time_to_index, index_to_time = create_trading_time_map()
        
        assert isinstance(time_to_index, dict)
        assert isinstance(index_to_time, dict)
        assert len(time_to_index) > 0
        assert len(index_to_time) > 0
        assert len(time_to_index) == len(index_to_time)
    
    def test_time_status_function(self):
        """测试时间状态函数"""
        from timely_data import get_time_status_and_sleep
        
        try:
            status, wait_seconds, next_session, message = get_time_status_and_sleep()
            
            # 验证返回值类型
            assert isinstance(status, str)
            assert isinstance(wait_seconds, (int, float))
            assert isinstance(next_session, str)
            assert isinstance(message, str)
            
            # 验证状态值
            assert status in ['trading', 'wait', 'exit']
            assert wait_seconds >= 0
            
        except Exception as e:
            pytest.fail(f"get_time_status_and_sleep函数执行失败: {e}")
    
    def test_format_time_duration(self):
        """测试时间格式化函数"""
        from timely_data import format_time_duration
        
        # 测试基本功能
        hours, minutes, seconds = format_time_duration(3661)  # 1小时1分1秒
        assert hours == 1
        assert minutes == 1
        assert seconds == 1
        
        # 测试零值
        hours, minutes, seconds = format_time_duration(0)
        assert hours == 0
        assert minutes == 0
        assert seconds == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])