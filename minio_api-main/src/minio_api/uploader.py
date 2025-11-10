"""
通用MinIO文件上传器 - 支持上传任意文件到指定路径
"""
import os
import io
import logging
from typing import Optional
from minio import Minio
from minio.error import S3Error

from .config import get_config, MinIOConfig

logger = logging.getLogger(__name__)

class MinIOFileUploader:
    """通用MinIO文件上传器"""
    
    def __init__(self, config: Optional[MinIOConfig] = None, **kwargs):
        """
        初始化MinIO上传器
        
        Args:
            config: MinIO配置对象，None则从环境变量读取
            **kwargs: 可选的配置覆盖参数
        """
        # 获取配置
        self.config = config or get_config()
        
        # 应用kwargs覆盖
        endpoint = kwargs.get('endpoint', self.config.endpoint)
        access_key = kwargs.get('access_key', self.config.access_key)
        secret_key = kwargs.get('secret_key', self.config.secret_key)
        secure = kwargs.get('secure', self.config.secure)
        
        # 初始化MinIO客户端
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        logger.info(f"初始化MinIO上传器: {endpoint} (secure={secure})")
    
    def upload_file(self,
                   bucket_name: str,
                   object_path: str,
                   file_path: str,
                   content_type: str = "application/octet-stream") -> bool:
        """
        上传本地文件到MinIO
        
        Args:
            bucket_name: 目标桶名称
            object_path: MinIO中的对象路径 (如: 'data/files/example.txt')
            file_path: 本地文件路径
            content_type: 文件内容类型
            
        Returns:
            bool: 上传是否成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"本地文件不存在: {file_path}")
                return False
            
            # 确保桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"创建桶: {bucket_name}")
            
            # 上传文件
            self.client.fput_object(
                bucket_name,
                object_path,
                file_path,
                content_type=content_type
            )
            
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            logger.info(f"上传成功: {bucket_name}/{object_path}, 大小: {file_size:.2f}MB")
            return True
            
        except S3Error as e:
            logger.error(f"上传文件失败: {e}")
            return False
    
    def upload_data(self,
                   bucket_name: str,
                   object_path: str,
                   data: bytes,
                   content_type: str = "application/octet-stream") -> bool:
        """
        上传二进制数据到MinIO
        
        Args:
            bucket_name: 目标桶名称
            object_path: MinIO中的对象路径
            data: 要上传的二进制数据
            content_type: 数据内容类型
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 确保桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"创建桶: {bucket_name}")
            
            # 将bytes数据包装成file-like对象
            data_stream = io.BytesIO(data)
            
            # 上传数据
            self.client.put_object(
                bucket_name,
                object_path,
                data_stream,
                len(data),
                content_type=content_type
            )
            
            data_size = len(data) / (1024 * 1024)  # MB
            logger.info(f"上传成功: {bucket_name}/{object_path}, 大小: {data_size:.2f}MB")
            return True
            
        except S3Error as e:
            logger.error(f"上传数据失败: {e}")
            return False
        except Exception as e:
            logger.error(f"上传数据时发生未知错误: {e}")
            return False

# 便捷函数
def upload_file_to_minio(bucket_name: str,
                        object_path: str,
                        file_path: str,
                        config: Optional[MinIOConfig] = None) -> bool:
    """
    上传文件到MinIO的便捷函数
    
    Args:
        bucket_name: 目标桶名称
        object_path: MinIO中的对象路径
        file_path: 本地文件路径
        config: MinIO配置
        
    Returns:
        bool: 上传是否成功
    """
    uploader = MinIOFileUploader(config=config)
    return uploader.upload_file(bucket_name, object_path, file_path)

def upload_data_to_minio(bucket_name: str,
                        object_path: str,
                        data: bytes,
                        content_type: str = "application/octet-stream",
                        config: Optional[MinIOConfig] = None) -> bool:
    """
    上传二进制数据到MinIO的便捷函数
    
    Args:
        bucket_name: 目标桶名称
        object_path: MinIO中的对象路径
        data: 要上传的二进制数据
        content_type: 数据内容类型
        config: MinIO配置
        
    Returns:
        bool: 上传是否成功
    """
    uploader = MinIOFileUploader(config=config)
    return uploader.upload_data(bucket_name, object_path, data, content_type)