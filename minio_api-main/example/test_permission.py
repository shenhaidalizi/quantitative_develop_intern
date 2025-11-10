#!/usr/bin/env python3
"""
MinIO 权限测试脚本 (修正版)
直接测试目标 bucket，避免 temp 权限问题
"""
import sys
import os
import io
import pandas as pd
import tempfile
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent if Path(__file__).parent.name == 'debug' else Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

try:
    from minio_api import MinIOStockDataClient, MinIOFileUploader
    from minio_api.config import reload_config, get_config
    from minio import Minio
    import logging
    
    # 设置日志级别
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

def test_bucket_permissions_direct(bucket_name: str, description: str) -> dict:
    """
    直接测试指定 bucket 的读写权限（避免 temp 权限问题）
    """
    print(f"\n{'='*60}")
    print(f"🧪 测试 {description} ({bucket_name}) 权限")
    print(f"{'='*60}")
    
    results = {
        'bucket_name': bucket_name,
        'description': description,
        'exists': False,
        'readable': False,
        'writable': False,
        'deletable': False,
        'error_messages': []
    }
    
    try:
        # 刷新配置
        reload_config()
        config = get_config()
        
        # 直接创建 MinIO 客户端，不通过 MinIOStockDataClient
        minio_client = Minio(
            endpoint=config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure
        )
        
        print(f"🔗 连接信息: {config.endpoint} (secure={config.secure})")
        
        # 1. 测试 bucket 是否存在
        print(f"📁 检查 bucket 是否存在...")
        try:
            exists = minio_client.bucket_exists(bucket_name)
            results['exists'] = exists
            if exists:
                print(f"✅ Bucket {bucket_name} 存在")
            else:
                print(f"❌ Bucket {bucket_name} 不存在")
                # 不尝试创建，直接返回
                return results
        except Exception as e:
            print(f"❌ 检查 bucket 存在性失败: {e}")
            results['error_messages'].append(f"检查bucket失败: {e}")
            return results
        
        # 2. 测试读权限 - 列出对象
        print(f"📖 测试读权限...")
        try:
            objects = list(minio_client.list_objects(bucket_name, recursive=True))
            object_count = len(objects)
            print(f"✅ 读权限正常，发现 {object_count} 个对象")
            results['readable'] = True
            
            # 显示前几个对象
            if object_count > 0:
                print(f"📋 前5个对象:")
                for i, obj in enumerate(objects[:5]):
                    size_mb = obj.size / (1024 * 1024) if obj.size else 0
                    print(f"   {i+1}. {obj.object_name} ({size_mb:.2f} MB)")
                if object_count > 5:
                    print(f"   ... 还有 {object_count - 5} 个对象")
        except Exception as e:
            print(f"❌ 读权限测试失败: {e}")
            results['error_messages'].append(f"读权限失败: {e}")
        
        # 3. 测试写权限 - 上传测试文件
        print(f"✍️  测试写权限...")
        test_file_path = f"test/permissions_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        test_content = f"权限测试文件\n创建时间: {datetime.now()}\nBucket: {bucket_name}\n"
        
        try:
            # 直接使用 minio_client 上传测试数据
            data_stream = io.BytesIO(test_content.encode('utf-8'))
            
            minio_client.put_object(
                bucket_name,
                test_file_path,
                data_stream,
                len(test_content.encode('utf-8')),
                content_type="text/plain"
            )
            
            print(f"✅ 写权限正常，已上传测试文件: {test_file_path}")
            results['writable'] = True
            
            # 4. 测试删除权限
            print(f"🗑️  测试删除权限...")
            try:
                minio_client.remove_object(bucket_name, test_file_path)
                print(f"✅ 删除权限正常，已删除测试文件")
                results['deletable'] = True
            except Exception as e:
                print(f"❌ 删除权限测试失败: {e}")
                results['error_messages'].append(f"删除权限失败: {e}")
                
        except Exception as e:
            print(f"❌ 写权限测试失败: {e}")
            results['error_messages'].append(f"写权限失败: {e}")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        results['error_messages'].append(f"测试错误: {e}")
    
    return results

def test_parquet_data_access():
    """
    测试 parquet 数据的读取权限（使用 data bucket）
    """
    print(f"\n{'='*60}")
    print(f"📊 测试 Parquet 数据读取权限")
    print(f"{'='*60}")
    
    results = {
        'can_read_parquet': False,
        'available_data_types': [],
        'sample_data_info': {},
        'error_messages': []
    }
    
    try:
        # 刷新配置
        reload_config()
        config = get_config()
        
        # 直接使用 data bucket 创建客户端
        client = MinIOStockDataClient(bucket_name=config.bucket_data)
        
        print(f"📋 检查可用数据类型...")
        try:
            available_data = client.list_available_data()
            data_types = available_data.get('data_types', [])
            file_count = available_data.get('file_count', 0)
            
            print(f"✅ 发现 {len(data_types)} 种数据类型，共 {file_count} 个文件")
            results['available_data_types'] = data_types
            results['can_read_parquet'] = len(data_types) > 0
            
            if data_types:
                print(f"📊 可用数据类型: {', '.join(data_types)}")
                
                # 尝试读取一些示例数据
                for data_type in data_types[:3]:  # 只测试前3种类型
                    print(f"\n📖 测试读取 {data_type} 数据...")
                    try:
                        # 获取一小段时间的数据进行测试
                        df = client.get_data(
                            data_type=data_type,
                            start_date="20240101",
                            end_date="20240107",  # 只获取一周的数据
                            symbols="all"
                        )
                        
                        if not df.empty:
                            print(f"✅ {data_type}: 成功读取 {len(df)} 行数据")
                            results['sample_data_info'][data_type] = {
                                'rows': len(df),
                                'columns': list(df.columns),
                                'date_range': f"{df.iloc[0]['trade_date'] if 'trade_date' in df.columns else 'N/A'} - {df.iloc[-1]['trade_date'] if 'trade_date' in df.columns else 'N/A'}"
                            }
                        else:
                            print(f"⚠️ {data_type}: 数据为空")
                            
                    except Exception as e:
                        print(f"❌ {data_type}: 读取失败 - {e}")
                        results['error_messages'].append(f"{data_type}读取失败: {e}")
            else:
                print(f"⚠️ 未发现任何可用数据类型")
                
        except Exception as e:
            print(f"❌ 检查可用数据失败: {e}")
            results['error_messages'].append(f"检查数据失败: {e}")
        
    except Exception as e:
        print(f"❌ Parquet 数据测试失败: {e}")
        results['error_messages'].append(f"Parquet测试失败: {e}")
    
    return results

def main():
    """
    主测试函数 (修正版)
    """
    print("🚀 MinIO 权限测试开始 (修正版)")
    print(f"⏰ 测试时间: {datetime.now()}")
    
    # 测试结果汇总
    all_results = {}
    
    try:
        # 获取配置信息
        config = get_config()
        all_buckets = config.get_all_buckets()
        print(f"\n📋 配置信息:")
        print(f"   Endpoint: {config.endpoint}")
        print(f"   Secure: {config.secure}")
        print(f"   配置的 Buckets: {all_buckets}")
        
    except Exception as e:
        print(f"❌ 获取配置失败: {e}")
        print("请检查 .env 文件配置")
        return
    
    # 1. 测试 mlresult bucket (result bucket)
    mlresult_results = test_bucket_permissions_direct(
        bucket_name=config.bucket_result, 
        description="MLResult (结果存储)"
    )
    all_results['mlresult'] = mlresult_results
    
    # 2. 测试 data bucket (parquet 数据) - 只测试权限，不测试数据读取
    data_bucket_results = test_bucket_permissions_direct(
        bucket_name=config.bucket_data, 
        description="Data (Parquet 数据存储)"
    )
    all_results['data_bucket'] = data_bucket_results
    
    # 3. 测试 parquet 数据读取（这个已经验证工作正常）
    parquet_results = test_parquet_data_access()
    all_results['parquet_data'] = parquet_results
    
    # 4. 生成测试报告
    print(f"\n{'='*60}")
    print(f"📋 测试报告汇总")
    print(f"{'='*60}")
    
    print(f"\n🏢 MLResult Bucket ({config.bucket_result}):")
    mlr = all_results['mlresult']
    print(f"   存在: {'✅' if mlr['exists'] else '❌'}")
    print(f"   读取: {'✅' if mlr['readable'] else '❌'}")
    print(f"   写入: {'✅' if mlr['writable'] else '❌'}")
    print(f"   删除: {'✅' if mlr['deletable'] else '❌'}")
    if mlr['error_messages']:
        print(f"   错误: {'; '.join(mlr['error_messages'])}")
    
    print(f"\n📊 Data Bucket ({config.bucket_data}):")
    db = all_results['data_bucket']
    print(f"   存在: {'✅' if db['exists'] else '❌'}")
    print(f"   读取: {'✅' if db['readable'] else '❌'}")
    print(f"   写入: {'✅' if db['writable'] else '❌'}")
    print(f"   删除: {'✅' if db['deletable'] else '❌'}")
    if db['error_messages']:
        print(f"   错误: {'; '.join(db['error_messages'])}")
    
    print(f"\n📈 Parquet 数据:")
    pd = all_results['parquet_data']
    print(f"   可读取: {'✅' if pd['can_read_parquet'] else '❌'}")
    print(f"   数据类型: {len(pd['available_data_types'])} 种")
    if pd['available_data_types']:
        print(f"   类型列表: {', '.join(pd['available_data_types'])}")
    if pd['sample_data_info']:
        print(f"   示例数据: {list(pd['sample_data_info'].keys())}")
    if pd['error_messages']:
        print(f"   错误: {'; '.join(pd['error_messages'])}")
    
    # 5. 总结
    print(f"\n{'='*60}")
    print(f"🎯 权限状态总结")
    print(f"{'='*60}")
    
    mlresult_writable = mlr['writable']
    mlresult_readable = mlr['readable'] 
    parquet_readable = db['readable'] and pd['can_read_parquet']
    parquet_writable = db['writable']
    
    print(f"📊 MLResult 权限:")
    print(f"   读取: {'✅' if mlresult_readable else '❌'}")
    print(f"   写入: {'✅' if mlresult_writable else '❌'}")
    
    print(f"📈 Parquet 权限:")
    print(f"   读取: {'✅' if parquet_readable else '❌'}")
    print(f"   写入: {'✅' if parquet_writable else '❌'}")
    
    # 根据用户期望验证结果
    expected_mlresult_w = mlresult_writable
    expected_mlresult_r = mlresult_readable
    expected_parquet_r = parquet_readable
    expected_parquet_w_deny = not parquet_writable
    
    if expected_mlresult_w and expected_mlresult_r and expected_parquet_r and expected_parquet_w_deny:
        print(f"\n🎉 权限配置符合预期!")
        print(f"   ✅ MLResult: 可读写")
        print(f"   ✅ Parquet: 只读")
    else:
        print(f"\n⚠️ 权限配置与预期不符:")
        print(f"   MLResult 写入: {'✅ 符合' if expected_mlresult_w else '❌ 应该可写'}")
        print(f"   MLResult 读取: {'✅ 符合' if expected_mlresult_r else '❌ 应该可读'}")
        print(f"   Parquet 读取: {'✅ 符合' if expected_parquet_r else '❌ 应该可读'}")
        print(f"   Parquet 写入禁止: {'✅ 符合' if expected_parquet_w_deny else '❌ 应该禁止写入'}")
    
    print(f"\n✅ 测试完成！")

if __name__ == "__main__":
    main()