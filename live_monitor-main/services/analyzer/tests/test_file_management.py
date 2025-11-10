#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件管理功能的脚本
使用pytest框架验证文件清理逻辑
"""

import pytest
import os
import sys
import pandas as pd
import tempfile
import shutil
from datetime import datetime, timedelta

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# 修正导入路径
from timely_data import manage_result_files, manage_index_files

class TestFileManagement:
    """文件管理测试类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        
        # 创建测试数据
        self.test_data = pd.DataFrame({
            'code': ['000001', '000002', '000003'],
            'Name': ['平安银行', '万科A', 'PT金田A'],
            'Price': [13.04, 6.64, 0.0],
            'Chg': [1.56, 1.53, 0.0],
            'Vol': [1041689, 891801, 0],
            'rolling1_z_score': [2.5, -1.8, 0.0],
            'rolling5_z_score': [1.9, -2.1, 0.0],
            'rolling10_z_score': [0.8, -1.5, 0.0],
            'rolling30_z_score': [0.3, -0.9, 0.0],
            'Chg5': [2.1, -1.2, 0.0],
            'Chg30': [3.5, -2.8, 0.0]
        })
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        # 删除临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_files(self, num_files=8, file_prefix="test_"):
        """创建测试文件"""
        created_files = []
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(num_files):
            file_time = base_time + timedelta(minutes=i*5)
            time_str = file_time.strftime('%H%M00')
            filename = f"{file_prefix}{time_str}_idx{i}.csv"
            filepath = os.path.join(self.test_dir, filename)
            
            # 保存文件
            self.test_data.to_csv(filepath, index=False)
            created_files.append(filename)
            
            # 设置文件修改时间
            timestamp = file_time.timestamp()
            os.utime(filepath, (timestamp, timestamp))
        
        return created_files
    
    def test_manage_result_files_basic(self):
        """测试基本文件管理功能"""
        # 创建8个测试文件
        created_files = self.create_test_files(8)
        
        # 验证文件创建成功
        csv_files_before = [f for f in os.listdir(self.test_dir) if f.endswith('.csv')]
        assert len(csv_files_before) == 8
        
        # 执行文件管理，保留5个文件
        manage_result_files(self.test_dir, max_files=5)
        
        # 验证文件管理结果
        csv_files_after = [f for f in os.listdir(self.test_dir) if f.endswith('.csv')]
        assert len(csv_files_after) == 5
        
        # 验证保留的是最新的文件
        csv_files_after.sort()
        expected_files = sorted(created_files)[-5:]  # 最新的5个文件
        assert sorted(csv_files_after) == expected_files
    
    def test_manage_result_files_no_deletion_needed(self):
        """测试文件数量未超限时不删除"""
        # 创建3个测试文件
        created_files = self.create_test_files(3)
        
        # 执行文件管理，保留5个文件
        manage_result_files(self.test_dir, max_files=5)
        
        # 验证没有文件被删除
        csv_files_after = [f for f in os.listdir(self.test_dir) if f.endswith('.csv')]
        assert len(csv_files_after) == 3
        assert sorted(csv_files_after) == sorted(created_files)
    
    def test_manage_result_files_empty_directory(self):
        """测试空目录的文件管理"""
        # 对空目录执行文件管理，应该不会报错
        manage_result_files(self.test_dir, max_files=5)
        
        # 验证目录仍然为空
        files = os.listdir(self.test_dir)
        assert len(files) == 0
    
    def test_manage_result_files_only_test_files(self):
        """测试只删除test_开头的CSV文件"""
        # 创建test_文件
        test_files = self.create_test_files(5, "test_")
        
        # 创建其他类型的文件
        other_files = []
        for i in range(3):
            filename = f"other_{i}.csv"
            filepath = os.path.join(self.test_dir, filename)
            self.test_data.to_csv(filepath, index=False)
            other_files.append(filename)
        
        # 创建非CSV文件
        txt_file = os.path.join(self.test_dir, "readme.txt")
        with open(txt_file, 'w') as f:
            f.write("test file")
        
        # 执行文件管理，保留3个文件
        manage_result_files(self.test_dir, max_files=3)
        
        # 验证只有test_开头的CSV文件被管理
        remaining_files = os.listdir(self.test_dir)
        test_csv_files = [f for f in remaining_files if f.startswith('test_') and f.endswith('.csv')]
        other_csv_files = [f for f in remaining_files if f.startswith('other_') and f.endswith('.csv')]
        
        assert len(test_csv_files) == 3  # test_文件被管理
        assert len(other_csv_files) == 3  # other_文件不受影响
        assert "readme.txt" in remaining_files  # 非CSV文件不受影响
    
    def test_manage_index_files_basic(self):
        """测试索引文件管理功能"""
        # 创建索引文件（不需要test_前缀）
        created_files = self.create_test_files(8, "index_")
        
        # 执行索引文件管理
        manage_index_files(self.test_dir, max_files=5)
        
        # 验证文件管理结果
        csv_files_after = [f for f in os.listdir(self.test_dir) if f.endswith('.csv')]
        assert len(csv_files_after) == 5
    
    def test_manage_index_files_directory_creation(self):
        """测试索引文件管理时自动创建目录"""
        nonexistent_dir = os.path.join(self.test_dir, "new_index_dir")
        
        # 对不存在的目录执行索引文件管理
        manage_index_files(nonexistent_dir, max_files=5)
        
        # 验证目录被创建
        assert os.path.exists(nonexistent_dir)
        assert os.path.isdir(nonexistent_dir)
    
    @pytest.mark.parametrize("max_files", [1, 3, 5, 10])
    def test_manage_result_files_various_limits(self, max_files):
        """参数化测试不同的文件数量限制"""
        # 创建10个测试文件
        created_files = self.create_test_files(10)
        
        # 执行文件管理
        manage_result_files(self.test_dir, max_files=max_files)
        
        # 验证结果
        csv_files_after = [f for f in os.listdir(self.test_dir) if f.endswith('.csv')]
        expected_count = min(max_files, 10)
        assert len(csv_files_after) == expected_count

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 