"""
MinIO文件上传器测试脚本 - 使用指定bucket
"""
import os
import tempfile
from datetime import datetime
from minio_api import MinIOFileUploader
from minio_api.config import get_config
from minio import Minio
import io

def test_uploader():
    """测试MinIO文件上传和读取"""
    
    # 使用配置中的result bucket
    config = get_config()
    bucket_name = config.bucket_result  # 这会从MINIO_BUCKET_RESULT读取，默认是mlresult
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_folder = f"test_{current_time}"
    
    print(f"🚀 开始测试MinIO文件上传...")
    print(f"📦 目标桶: {bucket_name} (类型: result)")
    print(f"📁 测试文件夹: {test_folder}")
    print(f"🔧 可用的bucket配置: {config.get_all_buckets()}")
    
    # 创建临时txt文件
    temp_file_content = f"""这是一个测试文件
创建时间: {datetime.now()}
测试文件夹: {test_folder}
目标bucket: {bucket_name}
用于测试MinIO文件上传和读取功能

Hello MinIO! 🌟
测试中文内容和特殊字符: !@#$%^&*()
"""
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(temp_file_content)
        temp_file_path = temp_file.name
    
    print(f"📝 创建临时文件: {temp_file_path}")
    print(f"📄 文件内容长度: {len(temp_file_content)} 字符")
    
    try:
        # 初始化上传器 - 直接指定bucket
        uploader = MinIOFileUploader()
        
        # 上传文件
        object_path = f"{test_folder}/tmp.txt"
        print(f"⬆️  正在上传文件到: {bucket_name}/{object_path}")
        
        upload_success = uploader.upload_file(
            bucket_name=bucket_name,
            object_path=object_path,
            file_path=temp_file_path,
            content_type="text/plain; charset=utf-8"
        )
        
        if upload_success:
            print("✅ 文件上传成功！")
        else:
            print("❌ 文件上传失败！")
            return
        
        # 读取刚上传的文件
        print(f"⬇️  正在从MinIO读取文件...")
        
        # 使用MinIO客户端读取文件
        client = Minio(
            endpoint=config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure
        )
        
        # 读取文件内容
        response = client.get_object(bucket_name, object_path)
        downloaded_content = response.read().decode('utf-8')
        response.close()
        
        print("✅ 文件读取成功！")
        print("📖 读取的文件内容:")
        print("-" * 50)
        print(downloaded_content)
        print("-" * 50)
        
        # 验证内容一致性
        if downloaded_content.strip() == temp_file_content.strip():
            print("✅ 内容验证成功：上传和下载的内容完全一致！")
        else:
            print("❌ 内容验证失败：上传和下载的内容不一致！")
            print("原始内容长度:", len(temp_file_content))
            print("下载内容长度:", len(downloaded_content))
        
        # 列出测试文件夹中的文件
        print(f"📂 列出 {test_folder} 文件夹中的文件:")
        objects = client.list_objects(bucket_name, prefix=f"{test_folder}/", recursive=True)
        for obj in objects:
            print(f"   📄 {obj.object_name} (大小: {obj.size} bytes)")
        
        # 额外测试：上传二进制数据
        print(f"🔧 测试上传二进制数据...")
        binary_data = f"二进制测试数据 - {current_time}".encode('utf-8')
        binary_object_path = f"{test_folder}/binary_test.bin"
        
        binary_upload_success = uploader.upload_data(
            bucket_name=bucket_name,
            object_path=binary_object_path,
            data=binary_data,
            content_type="application/octet-stream"
        )
        
        if binary_upload_success:
            print("✅ 二进制数据上传成功！")
            
            # 读取二进制数据
            bin_response = client.get_object(bucket_name, binary_object_path)
            downloaded_binary = bin_response.read()
            bin_response.close()
            
            if downloaded_binary == binary_data:
                print("✅ 二进制数据验证成功！")
            else:
                print("❌ 二进制数据验证失败！")
        
        print(f"\n🎉 测试完成！所有文件都在 {bucket_name}/{test_folder}/ 文件夹中")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_file_path)
            print(f"🧹 清理临时文件: {temp_file_path}")
        except:
            pass

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 MinIO文件上传器测试 - 多bucket支持")
    print("=" * 60)
    
    # 显示bucket配置
    config = get_config()
    print("📦 Bucket配置:")
    for bucket_type, bucket_name in config.get_all_buckets().items():
        print(f"   {bucket_type}: {bucket_name}")
    print()
    
    # 运行上传测试
    test_uploader()
    
    print("🏁 测试结束")
