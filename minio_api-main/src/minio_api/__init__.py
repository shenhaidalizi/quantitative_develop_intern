"""
MinIO API Package - 股票数据存储和分发 (多Schema支持版本)
"""
__version__ = "2.0.0"

from .client import (
    MinIOStockDataClient, 
    get_stock_data_from_minio,
    get_data_from_minio
)
from .uploader import MinIOFileUploader
from .downloader import (
    MinIOFileDownloader,
    download_file_from_minio,
    download_data_from_minio,
    get_object_stream_from_minio,
    get_object_info_from_minio
)
from .utils import (
    test_minio_connection,
    get_cnstock_data,
    get_cnstock_adj_factor_data, 
    get_cnstock_basic_data,
    get_cnindex_data,
    get_cnstock_moneyflow_data,
    list_supported_data_types,
    get_data_type_info,
    get_available_data_summary
)
from .schemas import (
    schema_manager,
    get_supported_data_types,
    is_data_type_supported,
    get_data_type_path,
    get_data_type_config
)
from .tick_client import (
    MinIOTickDataClient,
    get_tick_data_from_minio
)



__all__ = [
    # 主要客户端类
    'MinIOStockDataClient',
    'MinIOFileUploader',
    'MinIOFileDownloader',
    'MinIOTickDataClient',
    # 数据获取函数
    'get_stock_data_from_minio',  # 兼容性函数
    'get_data_from_minio',        # 新的通用函数
    'get_tick_data_from_minio',
    'get_cnstock_data',
    'get_cnstock_adj_factor_data',
    'get_cnstock_basic_data', 
    'get_cnindex_data',
    'get_cnstock_moneyflow_data',
    
    # 文件操作便捷函数
    'download_file_from_minio',
    'download_data_from_minio', 
    'get_object_stream_from_minio',
    'get_object_info_from_minio',
    
    # 工具函数
    'test_minio_connection',
    'list_supported_data_types',
    'get_data_type_info',
    'get_available_data_summary',
    
    # Schema管理
    'schema_manager',
    'get_supported_data_types',
    'is_data_type_supported',
    'get_data_type_path',
    'get_data_type_config',
]
