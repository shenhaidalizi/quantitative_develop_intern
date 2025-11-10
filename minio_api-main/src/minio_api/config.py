"""
配置管理模块 - 多bucket支持版本
"""
import os
from typing import Optional, Dict
from pathlib import Path
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class MinIOConfig:
    """MinIO配置类 - 支持多bucket配置"""
    
    def __init__(self, env_file: Optional[str] = None, skip_validation: bool = False):
        """
        初始化配置
        
        Args:
            env_file: .env文件路径，None则自动查找
            skip_validation: 是否跳过配置验证（测试用）
        """
        self._load_env_file(env_file)
        if not skip_validation:
            self._validate_config()
    
    def _load_env_file(self, env_file: Optional[str] = None):
        """加载.env文件"""
        if env_file:
            env_path = Path(env_file)
        else:
            # 自动查找.env文件
            current_dir = Path.cwd()
            env_path = None
            
            # 向上查找.env文件
            for parent in [current_dir] + list(current_dir.parents):
                potential_env = parent / '.env'
                if potential_env.exists():
                    env_path = potential_env
                    break
        
        if env_path and env_path.exists():
            load_dotenv(env_path)
            logger.info(f"加载环境配置文件: {env_path}")
        else:
            logger.warning("未找到.env文件，将使用系统环境变量")
    
    def _validate_config(self):
        """验证必需的配置项"""
        required_vars = ['MINIO_ENDPOINT', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            value = os.getenv(var)
            # 检查是否为None或空字符串
            if not value or value.strip() == '':
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"缺少必需的环境变量: {missing_vars}")
    
    @property
    def endpoint(self) -> str:
        """MinIO服务器端点"""
        value = os.getenv('MINIO_ENDPOINT')
        if not value:
            raise ValueError("MINIO_ENDPOINT 未配置")
        return value
    
    @property
    def access_key(self) -> str:
        """MinIO访问密钥"""
        value = os.getenv('MINIO_ACCESS_KEY')
        if not value:
            raise ValueError("MINIO_ACCESS_KEY 未配置")
        return value
    
    @property
    def secret_key(self) -> str:
        """MinIO秘密密钥"""
        value = os.getenv('MINIO_SECRET_KEY')
        if not value:
            raise ValueError("MINIO_SECRET_KEY 未配置")
        return value
    
    @property
    def secure(self) -> bool:
        """是否使用HTTPS"""
        return os.getenv('MINIO_SECURE', 'false').lower() in ('true', '1', 'yes')
    
    @property
    def bucket_data(self) -> str:
        """数据桶名称"""
        return os.getenv('MINIO_BUCKET_DATA', 'parquet2')
    
    @property
    def bucket_trader_data(self) -> str:
        """交易辅助数据桶名称（localdata 使用）"""
        return os.getenv('MINIO_BUCKET_TRADER_DATA', 'trader-data')
    
    @property
    def bucket_result(self) -> str:
        """结果桶名称"""
        return os.getenv('MINIO_BUCKET_RESULT', 'mlresult')
    
    @property
    def bucket_backup(self) -> str:
        """备份桶名称"""
        return os.getenv('MINIO_BUCKET_BACKUP', 'backup')
    
    @property
    def bucket_temp(self) -> str:
        """临时文件桶名称"""
        return os.getenv('MINIO_BUCKET_TEMP', 'temp')
    
    def get_bucket(self, bucket_type: str = 'temp') -> str:
        """
        根据类型获取bucket名称
        
        Args:
            bucket_type: bucket类型 ('data', 'trader_data', 'result', 'backup', 'temp', 'default')
            
        Returns:
            bucket名称
        """
        bucket_map = {
            'data': self.bucket_data,
            'trader_data': self.bucket_trader_data,
            'result': self.bucket_result, 
            'backup': self.bucket_backup,
            'temp': self.bucket_temp,
            'default': self.bucket_temp  # default指向temp
        }
        
        if bucket_type not in bucket_map:
            raise ValueError(f"不支持的bucket类型: {bucket_type}, 支持的类型: {list(bucket_map.keys())}")
        
        return bucket_map[bucket_type]
    
    def get_all_buckets(self) -> Dict[str, str]:
        """获取所有配置的bucket"""
        return {
            'data': self.bucket_data,
            'trader_data': self.bucket_trader_data,
            'result': self.bucket_result,
            'backup': self.bucket_backup,
            'temp': self.bucket_temp
        }
    
    @property
    def region(self) -> Optional[str]:
        """MinIO区域"""
        return os.getenv('MINIO_REGION')
    
    @property
    def timeout(self) -> int:
        """连接超时时间（秒）"""
        return int(os.getenv('MINIO_TIMEOUT', '60'))
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'endpoint': self.endpoint,
            'access_key': self.access_key,
            'secret_key': self.secret_key,
            'secure': self.secure,
            'buckets': self.get_all_buckets(),
            'region': self.region,
            'timeout': self.timeout
        }
    
    def __repr__(self) -> str:
        buckets = list(self.get_all_buckets().values())
        return f"MinIOConfig(endpoint='{self.endpoint}', buckets={buckets}, secure={self.secure})"

# 全局配置实例
_config = None

def get_config(env_file: Optional[str] = None, force_reload: bool = False) -> MinIOConfig:
    """
    获取全局配置实例
    
    Args:
        env_file: .env文件路径
        force_reload: 是否强制重新加载配置
        
    Returns:
        MinIOConfig: 配置实例
    """
    global _config
    if _config is None or force_reload:
        _config = MinIOConfig(env_file)
    return _config

def reload_config(env_file: Optional[str] = None):
    """重新加载配置"""
    global _config
    _config = MinIOConfig(env_file)
    return _config

def clear_config():
    """清除全局配置缓存（测试用）"""
    global _config
    _config = None