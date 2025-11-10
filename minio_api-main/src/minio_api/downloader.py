"""
通用MinIO文件下载器 - 支持下载任意文件到本地或内存
"""
import os
import io
import logging
from typing import Optional, Union
from pathlib import Path
from minio import Minio
from minio.error import S3Error

from .config import get_config, MinIOConfig

logger = logging.getLogger(__name__)

class MinIOFileDownloader:
    """通用MinIO文件下载器"""
    
    def __init__(self, config: Optional[MinIOConfig] = None, **kwargs):
        """
        初始化MinIO下载器
        
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
        
        logger.info(f"初始化MinIO下载器: {endpoint} (secure={secure})")
    
    def download_file(self,
                     bucket_name: str,
                     object_path: str,
                     file_path: str,
                     create_dirs: bool = True) -> bool:
        """
        从MinIO下载文件到本地
        
        Args:
            bucket_name: 源桶名称
            object_path: MinIO中的对象路径 (如: 'data/files/example.txt')
            file_path: 本地保存路径
            create_dirs: 是否自动创建目录
            
        Returns:
            bool: 下载是否成功
        """
        try:
            # 检查桶是否存在
            if not self.client.bucket_exists(bucket_name):
                logger.error(f"桶不存在: {bucket_name}")
                return False
            
            # 检查对象是否存在
            try:
                self.client.stat_object(bucket_name, object_path)
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    logger.error(f"对象不存在: {bucket_name}/{object_path}")
                    return False
                raise
            
            # 自动创建目录
            if create_dirs:
                file_dir = Path(file_path).parent
                file_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            self.client.fget_object(
                bucket_name,
                object_path,
                file_path
            )
            
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            logger.info(f"下载成功: {bucket_name}/{object_path} -> {file_path}, 大小: {file_size:.2f}MB")
            return True
            
        except S3Error as e:
            logger.error(f"下载文件失败: {e}")
            return False
        except Exception as e:
            logger.error(f"下载文件时发生未知错误: {e}")
            return False
    
    def download_data(self,
                     bucket_name: str,
                     object_path: str) -> Optional[bytes]:
        """
        从MinIO下载文件为二进制数据
        
        Args:
            bucket_name: 源桶名称
            object_path: MinIO中的对象路径
            
        Returns:
            bytes: 文件二进制数据，失败返回None
        """
        try:
            # 检查桶是否存在
            if not self.client.bucket_exists(bucket_name):
                logger.error(f"桶不存在: {bucket_name}")
                return None
            
            # 检查对象是否存在并获取文件
            response = self.client.get_object(bucket_name, object_path)
            data = response.read()
            response.close()
            
            data_size = len(data) / (1024 * 1024)  # MB
            logger.info(f"下载成功: {bucket_name}/{object_path}, 大小: {data_size:.2f}MB")
            return data
            
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.error(f"对象不存在: {bucket_name}/{object_path}")
            else:
                logger.error(f"下载数据失败: {e}")
            return None
        except Exception as e:
            logger.error(f"下载数据时发生错误: {e}")
            return None
    
    def get_object_stream(self,
                         bucket_name: str,
                         object_path: str) -> Optional[io.BytesIO]:
        """
        获取MinIO对象作为内存中的file-like对象
        
        Args:
            bucket_name: 源桶名称
            object_path: MinIO中的对象路径
            
        Returns:
            io.BytesIO: file-like对象，可以像文件一样操作，失败返回None
        """
        try:
            # 下载数据
            data = self.download_data(bucket_name, object_path)
            if data is None:
                return None
            
            # 包装成file-like对象
            file_obj = io.BytesIO(data)
            file_obj.seek(0)  # 重置指针到开头
            
            logger.info(f"获取对象流成功: {bucket_name}/{object_path}")
            return file_obj
            
        except Exception as e:
            logger.error(f"获取对象流时发生错误: {e}")
            return None
    
    def get_object_info(self,
                       bucket_name: str,
                       object_path: str) -> Optional[dict]:
        """
        获取对象信息
        
        Args:
            bucket_name: 桶名称
            object_path: 对象路径
            
        Returns:
            dict: 对象信息，包含大小、修改时间等
        """
        try:
            stat = self.client.stat_object(bucket_name, object_path)
            return {
                'object_name': stat.object_name,
                'size': stat.size,
                'size_mb': stat.size / (1024 * 1024),
                'last_modified': stat.last_modified,
                'etag': stat.etag,
                'content_type': stat.content_type
            }
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.error(f"对象不存在: {bucket_name}/{object_path}")
            else:
                logger.error(f"获取对象信息失败: {e}")
            return None
    
    def list_objects(self,
                    bucket_name: str,
                    prefix: str = "",
                    recursive: bool = True) -> list:
        """
        列出桶中的对象
        
        Args:
            bucket_name: 桶名称
            prefix: 对象前缀过滤
            recursive: 是否递归列出子目录
            
        Returns:
            list: 对象列表
        """
        try:
            objects = []
            for obj in self.client.list_objects(bucket_name, prefix=prefix, recursive=recursive):
                objects.append({
                    'object_name': obj.object_name,
                    'size': obj.size,
                    'size_mb': obj.size / (1024 * 1024),
                    'last_modified': obj.last_modified,
                    'etag': obj.etag
                })
            return objects
        except S3Error as e:
            logger.error(f"列出对象失败: {e}")
            return []

# 便捷函数
def download_file_from_minio(bucket_name: str,
                           object_path: str,
                           file_path: str,
                           config: Optional[MinIOConfig] = None,
                           create_dirs: bool = True) -> bool:
    """
    从MinIO下载文件的便捷函数
    
    Args:
        bucket_name: 源桶名称
        object_path: MinIO中的对象路径
        file_path: 本地保存路径
        config: MinIO配置
        create_dirs: 是否自动创建目录
        
    Returns:
        bool: 下载是否成功
    """
    downloader = MinIOFileDownloader(config=config)
    return downloader.download_file(bucket_name, object_path, file_path, create_dirs)

def download_data_from_minio(bucket_name: str,
                           object_path: str,
                           config: Optional[MinIOConfig] = None) -> Optional[bytes]:
    """
    从MinIO下载数据的便捷函数
    
    Args:
        bucket_name: 源桶名称
        object_path: MinIO中的对象路径
        config: MinIO配置
        
    Returns:
        bytes: 文件二进制数据，失败返回None
    """
    downloader = MinIOFileDownloader(config=config)
    return downloader.download_data(bucket_name, object_path)

def get_object_stream_from_minio(bucket_name: str,
                                object_path: str,
                                config: Optional[MinIOConfig] = None) -> Optional[io.BytesIO]:
    """
    获取MinIO对象流的便捷函数
    
    Args:
        bucket_name: 源桶名称
        object_path: MinIO中的对象路径
        config: MinIO配置
        
    Returns:
        io.BytesIO: file-like对象
    """
    downloader = MinIOFileDownloader(config=config)
    return downloader.get_object_stream(bucket_name, object_path)

def get_object_info_from_minio(bucket_name: str,
                              object_path: str,
                              config: Optional[MinIOConfig] = None) -> Optional[dict]:
    """
    获取MinIO对象信息的便捷函数
    
    Args:
        bucket_name: 桶名称
        object_path: 对象路径
        config: MinIO配置
        
    Returns:
        dict: 对象信息
    """
    downloader = MinIOFileDownloader(config=config)
    return downloader.get_object_info(bucket_name, object_path)
