"""
MinIO文件下载器测试脚本 - 展示各种下载方式
"""
import os
import tempfile
import pandas as pd
from datetime import datetime
from pathlib import Path
from minio_api import MinIOFileUploader, MinIOFileDownloader
from minio_api.config import get_config

def test_downloader():
    """测试MinIO文件下载功能"""
    
    # 使用配置中的result bucket
    config = get_config()
    bucket_name = config.bucket_result  # 默认是mlresult
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_folder = f"download_test_{current_time}"
    
    print(f"🚀 开始测试MinIO文件下载...")
    print(f"📦 目标桶: {bucket_name}")
    print(f"📁 测试文件夹: {test_folder}")
    
    # 初始化上传器和下载器
    uploader = MinIOFileUploader()
    downloader = MinIOFileDownloader()
    
    # 准备测试数据
    test_data = {
        "text_file": {
            "content": f"""测试文本文件 - {current_time}
这是一个用于测试下载功能的文本文件。
创建时间: {datetime.now()}
包含中文和特殊字符: !@#$%^&*()
""",
            "object_path": f"{test_folder}/test.txt",
            "content_type": "text/plain; charset=utf-8"
        },
        "csv_file": {
            "content": """name,age,city
张三,25,北京
李四,30,上海
王五,28,广州
赵六,35,深圳""",
            "object_path": f"{test_folder}/test.csv",
            "content_type": "text/csv"
        },
        "binary_file": {
            "content": f"二进制测试数据 - {current_time} 🌟".encode('utf-8'),
            "object_path": f"{test_folder}/test.bin",
            "content_type": "application/octet-stream"
        }
    }
    
    temp_files = []
    
    try:
        # 1. 准备测试文件 - 上传一些文件供下载测试
        print("\n📤 第一步：准备测试文件...")
        
        for file_type, file_info in test_data.items():
            if file_type == "binary_file":
                # 二进制数据直接上传
                success = uploader.upload_data(
                    bucket_name=bucket_name,
                    object_path=file_info["object_path"],
                    data=file_info["content"],
                    content_type=file_info["content_type"]
                )
            else:
                # 文本数据先创建临时文件再上传
                with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_type.split("_")[0]}', 
                                               delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(file_info["content"])
                    temp_file_path = temp_file.name
                    temp_files.append(temp_file_path)
                
                success = uploader.upload_file(
                    bucket_name=bucket_name,
                    object_path=file_info["object_path"],
                    file_path=temp_file_path,
                    content_type=file_info["content_type"]
                )
            
            if success:
                print(f"✅ {file_type} 上传成功: {file_info['object_path']}")
            else:
                print(f"❌ {file_type} 上传失败")
                return
        
        # 2. 测试下载到本地文件
        print(f"\n📥 第二步：测试下载到本地文件...")
        download_dir = Path(tempfile.gettempdir()) / f"minio_downloads_{current_time}"
        
        for file_type, file_info in test_data.items():
            local_path = download_dir / Path(file_info["object_path"]).name
            
            success = downloader.download_file(
                bucket_name=bucket_name,
                object_path=file_info["object_path"],
                file_path=str(local_path),
                create_dirs=True
            )
            
            if success:
                print(f"✅ {file_type} 下载成功: {local_path}")
                # 验证文件内容
                if file_type == "binary_file":
                    with open(local_path, 'rb') as f:
                        downloaded = f.read()
                    original = file_info["content"]
                else:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        downloaded = f.read()
                    original = file_info["content"]
                
                if downloaded == original:
                    print(f"   📋 内容验证成功")
                else:
                    print(f"   ❌ 内容验证失败")
            else:
                print(f"❌ {file_type} 下载失败")
        
        # 3. 测试下载为二进制数据
        print(f"\n💾 第三步：测试下载为二进制数据...")
        
        for file_type, file_info in test_data.items():
            data = downloader.download_data(
                bucket_name=bucket_name,
                object_path=file_info["object_path"]
            )
            
            if data is not None:
                print(f"✅ {file_type} 数据下载成功, 大小: {len(data)} bytes")
                
                # 对于文本文件，展示解码后的内容片段
                if file_type in ["text_file", "csv_file"]:
                    try:
                        text_content = data.decode('utf-8')
                        preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                        print(f"   📄 内容预览: {preview}")
                    except UnicodeDecodeError:
                        print(f"   📄 二进制数据，无法解码为文本")
            else:
                print(f"❌ {file_type} 数据下载失败")
        
        # 4. 测试获取file-like对象
        print(f"\n🔗 第四步：测试获取file-like对象...")
        
        # 测试CSV文件的stream读取
        csv_path = test_data["csv_file"]["object_path"]
        file_stream = downloader.get_object_stream(
            bucket_name=bucket_name,
            object_path=csv_path
        )
        
        if file_stream is not None:
            print(f"✅ 获取CSV file-like对象成功")
            
            # 使用pandas直接从stream读取
            try:
                file_stream.seek(0)  # 重置到开头
                df = pd.read_csv(file_stream)
                print(f"   📊 使用pandas读取CSV成功:")
                print(f"      行数: {len(df)}, 列数: {len(df.columns)}")
                print(f"      列名: {list(df.columns)}")
                print(f"      数据预览:")
                print(df.head().to_string(index=False).replace('\n', '\n      '))
            except Exception as e:
                print(f"   ❌ pandas读取失败: {e}")
        else:
            print(f"❌ 获取CSV file-like对象失败")
        
        # 5. 测试获取对象信息
        print(f"\n📋 第五步：测试获取对象信息...")
        
        for file_type, file_info in test_data.items():
            info = downloader.get_object_info(
                bucket_name=bucket_name,
                object_path=file_info["object_path"]
            )
            
            if info:
                print(f"✅ {file_type} 对象信息:")
                print(f"   📄 对象名: {info['object_name']}")
                print(f"   📏 大小: {info['size']} bytes ({info['size_mb']:.3f} MB)")
                print(f"   🕐 修改时间: {info['last_modified']}")
                print(f"   📝 内容类型: {info['content_type']}")
                print(f"   🏷️  ETag: {info['etag']}")
            else:
                print(f"❌ {file_type} 获取对象信息失败")
        
        # 6. 测试列出对象
        print(f"\n📂 第六步：列出测试文件夹中的所有对象...")
        
        objects = downloader.list_objects(
            bucket_name=bucket_name,
            prefix=f"{test_folder}/",
            recursive=True
        )
        
        print(f"找到 {len(objects)} 个对象:")
        for obj in objects:
            print(f"   📄 {obj['object_name']}")
            print(f"      大小: {obj['size']} bytes ({obj['size_mb']:.3f} MB)")
            print(f"      修改时间: {obj['last_modified']}")
        
        # 7. 便捷函数测试
        print(f"\n🛠️  第七步：测试便捷函数...")
        
        from minio_api import (
            download_file_from_minio, 
            download_data_from_minio, 
            get_object_stream_from_minio,
            get_object_info_from_minio
        )
        
        # 测试便捷下载函数
        test_file_path = download_dir / "convenience_test.txt"
        success = download_file_from_minio(
            bucket_name=bucket_name,
            object_path=test_data["text_file"]["object_path"],
            file_path=str(test_file_path)
        )
        
        if success:
            print(f"✅ 便捷下载函数测试成功: {test_file_path}")
        else:
            print(f"❌ 便捷下载函数测试失败")
        
        # 测试便捷数据获取函数
        data = download_data_from_minio(
            bucket_name=bucket_name,
            object_path=test_data["text_file"]["object_path"]
        )
        
        if data:
            print(f"✅ 便捷数据获取函数测试成功, 大小: {len(data)} bytes")
        else:
            print(f"❌ 便捷数据获取函数测试失败")
        
        print(f"\n🎉 所有下载测试完成！文件保存在: {download_dir}")
        print(f"📁 MinIO中的测试文件位于: {bucket_name}/{test_folder}/")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理临时文件
        for temp_file_path in temp_files:
            try:
                os.unlink(temp_file_path)
                print(f"🧹 清理临时文件: {temp_file_path}")
            except:
                pass

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 MinIO文件下载器功能测试")
    print("=" * 70)
    
    # 显示配置信息
    config = get_config()
    print("⚙️  配置信息:")
    print(f"   端点: {config.endpoint}")
    print(f"   安全连接: {config.secure}")
    print("📦 Bucket配置:")
    for bucket_type, bucket_name in config.get_all_buckets().items():
        print(f"   {bucket_type}: {bucket_name}")
    print()
    
    # 运行测试
    test_downloader()
    
    print("\n🏁 测试结束")
