#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行所有测试的便捷脚本
"""

import sys
import os

def check_environment():
    """检查测试环境"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    
    print("🔍 检查测试环境...")
    
    # 检查重要文件
    important_files = ['timely_data.py', 'preprocess_data.py']
    missing_files = []
    
    for filename in important_files:
        file_path = os.path.join(parent_dir, filename)
        if not os.path.exists(file_path):
            missing_files.append(filename)
        else:
            print(f"✅ 找到文件: {filename}")
    
    if missing_files:
        print(f"❌ 缺失文件: {missing_files}")
        return False
    
    # 检查模块导入
    try:
        import timely_data
        print("✅ timely_data模块导入成功")
    except ImportError as e:
        print(f"❌ timely_data模块导入失败: {e}")
        return False
    
    try:
        import preprocess_data
        print("✅ preprocess_data模块导入成功")
    except ImportError as e:
        print(f"❌ preprocess_data模块导入失败: {e}")
        return False
    
    return True

def main():
    """运行所有测试"""
    try:
        import pytest
        
        print("🧪 股票分析系统测试套件")
        print("=" * 60)
        
        # 检查环境
        if not check_environment():
            print("❌ 环境检查失败，请检查项目文件")
            return 1
        
        print("\n🚀 开始运行测试...")
        print("-" * 60)
        
        # 获取测试目录
        test_dir = os.path.dirname(__file__)
        
        # 先运行基础测试
        print("📋 运行基础功能测试...")
        basic_exit_code = pytest.main([
            os.path.join(test_dir, "test_basic.py"),
            "-v",
            "--tb=short",
            "--disable-warnings"
        ])
        
        if basic_exit_code != 0:
            print("❌ 基础测试失败，停止执行")
            return basic_exit_code
        
        print("\n📋 运行全部测试...")
        # 运行所有测试
        exit_code = pytest.main([
            test_dir,
            "-v",
            "--tb=short",
            "--color=yes",
            "--disable-warnings",
            # 不使用 -x 参数，让所有测试都运行
        ])
        
        print("\n" + "=" * 60)
        if exit_code == 0:
            print("✅ 所有测试通过！")
        else:
            print(f"⚠️ 部分测试失败，退出代码: {exit_code}")
            print("💡 请检查失败的测试并修复相关问题")
        print("=" * 60)
        
        return exit_code
        
    except ImportError:
        print("❌ 请先安装pytest:")
        print("pip install pytest")
        print("\n可选的额外包:")
        print("pip install pytest-cov pytest-mock")
        return 1
    except Exception as e:
        print(f"❌ 运行测试时发生错误: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 