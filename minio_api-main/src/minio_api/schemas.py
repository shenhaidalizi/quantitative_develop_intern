"""
Schema管理模块 - 整合不同数据源的schema定义
基于data_dev的schema设计，提供统一的数据类型支持
"""
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据类型到路径的映射
# 基于shared_definitions.py的PARQUET_PATHS
DATA_TYPE_PATHS = {
    'CNSTOCK': 'daily/cnstock',
    'CNSTOCK_ADJ': 'daily/cnstock_adj', 
    'CNSTOCK_BASIC': 'daily/cnstock_basic',
    'CNINDEX': 'daily/cnindex',
    'CNSTOCK_MONEYFLOW': 'daily/cnstock_moneyflow',
    'SWINDEX': 'daily/swindex',
    'CNFUND': 'daily/cnfund',
    'CNFUND_ADJ': 'daily/cnfund_adj',
    'CNFUT': 'daily/cnfut',
    'CNSTOCK_LIMIT': 'daily/cnstock_limit',
    'CNSTOCK_MARGIN_DETAIL': 'daily/cnstock_margin_detail',
    'CIINDEX': 'daily/ciindex',
    'THSINDEX': 'daily/thsindex',
    'GLOBALINDEX': 'daily/globalindex',
    'CNINDEX_BASIC': 'daily/cnindex_basic',
    'CNMARKET_STATS': 'daily/cnmarket_stats',
    'CNFINA_INDICATOR': 'daily/cnfina_indicator',
    'OPT_DAILY': 'daily/opt',
}

# 数据类型的基础配置
# 基于converter_daily_schema.py的定义
DATA_TYPE_CONFIG = {
    'CNSTOCK': {
        'date_column': 'trade_date',
        'symbol_column': 'ts_code',
        'description': '中国股票日线数据',
        'schema': {
            'ts_code': {'dtype': 'str'},
            'trade_date': {'dtype': 'datetime64[ns]'},
            'open': {'dtype': 'float64'},
            'high': {'dtype': 'float64'},
            'low': {'dtype': 'float64'},
            'close': {'dtype': 'float64'},
            'vol': {'dtype': 'int64', 'fillna': 0},
            'amount': {'dtype': 'float64'},
            'pre_close': {'dtype': 'float64'},
            'change': {'dtype': 'float64'},
            'pct_chg': {'dtype': 'float64'},
        }
    },
    'CNSTOCK_ADJ': {
        'date_column': 'trade_date',
        'symbol_column': 'ts_code',
        'description': '中国股票复权数据',
        'schema': {
            'ts_code': {'dtype': 'str'},
            'trade_date': {'dtype': 'datetime64[ns]'},
            'open': {'dtype': 'float64'},
            'high': {'dtype': 'float64'},
            'low': {'dtype': 'float64'},
            'close': {'dtype': 'float64'},
            'vol': {'dtype': 'int64', 'fillna': 0},
            'amount': {'dtype': 'float64'},
            'adj_factor': {'dtype': 'float64'},
        }
    },
    'CNSTOCK_BASIC': {
        'date_column': 'trade_date',
        'symbol_column': 'ts_code',
        'description': '中国股票基础信息',
        'schema': {
            'ts_code': {'dtype': 'str'},
            'trade_date': {'dtype': 'datetime64[ns]'},
            'close': {'dtype': 'float64'},
            'turnover_rate': {'dtype': 'float64'},
            'turnover_rate_f': {'dtype': 'float64'},
            'volume_ratio': {'dtype': 'float64'},
            'pe': {'dtype': 'float64'},
            'pe_ttm': {'dtype': 'float64'},
            'pb': {'dtype': 'float64'},
            'ps': {'dtype': 'float64'},
            'ps_ttm': {'dtype': 'float64'},
            'dv_ratio': {'dtype': 'float64'},
            'dv_ttm': {'dtype': 'float64'},
            'total_share': {'dtype': 'float64'},
            'float_share': {'dtype': 'float64'},
            'free_share': {'dtype': 'float64'},
            'total_mv': {'dtype': 'float64'},
            'circ_mv': {'dtype': 'float64'},
        }
    },
    'CNINDEX': {
        'date_column': 'trade_date',
        'symbol_column': 'ts_code',
        'description': '中国指数数据',
        'schema': {
            'ts_code': {'dtype': 'str'},
            'trade_date': {'dtype': 'datetime64[ns]'},
            'open': {'dtype': 'float64'},
            'high': {'dtype': 'float64'},
            'low': {'dtype': 'float64'},
            'close': {'dtype': 'float64'},
            'vol': {'dtype': 'int64', 'fillna': 0},
            'amount': {'dtype': 'float64'},
            'pre_close': {'dtype': 'float64'},
            'change': {'dtype': 'float64'},
            'pct_chg': {'dtype': 'float64'},
            'year': {'dtype': 'int32', 'fillna': 0},
            'month': {'dtype': 'int32', 'fillna': 0},
        }
    },
    'CNSTOCK_MONEYFLOW': {
        'date_column': 'trade_date',
        'symbol_column': 'ts_code',
        'description': '中国股票资金流向数据',
        'schema': {
            'ts_code': {'dtype': 'str'},
            'trade_date': {'dtype': 'datetime64[ns]'},
            'buy_sm_vol': {'dtype': 'int64', 'fillna': 0},
            'buy_sm_amount': {'dtype': 'float64', 'fillna': 0.0},
            'sell_sm_vol': {'dtype': 'int64', 'fillna': 0},
            'sell_sm_amount': {'dtype': 'float64', 'fillna': 0.0},
            'buy_md_vol': {'dtype': 'int64', 'fillna': 0},
            'buy_md_amount': {'dtype': 'float64', 'fillna': 0.0},
            'sell_md_vol': {'dtype': 'int64', 'fillna': 0},
            'sell_md_amount': {'dtype': 'float64', 'fillna': 0.0},
            'buy_lg_vol': {'dtype': 'int64', 'fillna': 0},
            'buy_lg_amount': {'dtype': 'float64', 'fillna': 0.0},
            'sell_lg_vol': {'dtype': 'int64', 'fillna': 0},
            'sell_lg_amount': {'dtype': 'float64', 'fillna': 0.0},
            'buy_elg_vol': {'dtype': 'int64', 'fillna': 0},
            'buy_elg_amount': {'dtype': 'float64', 'fillna': 0.0},
            'sell_elg_vol': {'dtype': 'int64', 'fillna': 0},
            'sell_elg_amount': {'dtype': 'float64', 'fillna': 0.0},
            'net_mf_vol': {'dtype': 'int64', 'fillna': 0},
            'net_mf_amount': {'dtype': 'float64', 'fillna': 0.0},
        }
    }
}

class SchemaManager:
    """Schema管理器 - 提供统一的数据类型支持"""
    
    def __init__(self):
        self.supported_types = list(DATA_TYPE_PATHS.keys())
        self.priority_types = ['CNSTOCK', 'CNSTOCK_ADJ', 'CNSTOCK_BASIC', 'CNINDEX', 'CNSTOCK_MONEYFLOW']
    
    def get_supported_types(self) -> List[str]:
        """获取所有支持的数据类型"""
        return self.supported_types.copy()
    
    def get_priority_types(self) -> List[str]:
        """获取优先支持的数据类型"""
        return self.priority_types.copy()
    
    def is_supported(self, data_type: str) -> bool:
        """检查数据类型是否支持"""
        return data_type in self.supported_types
    
    def get_path_prefix(self, data_type: str) -> str:
        """获取数据类型对应的MinIO路径前缀"""
        if not self.is_supported(data_type):
            raise ValueError(f"不支持的数据类型: {data_type}")
        return DATA_TYPE_PATHS[data_type]
    
    def get_config(self, data_type: str) -> Dict[str, Any]:
        """获取数据类型的配置信息"""
        if not self.is_supported(data_type):
            raise ValueError(f"不支持的数据类型: {data_type}")
        
        # 返回基础配置，如果没有定义则使用默认配置
        return DATA_TYPE_CONFIG.get(data_type, {
            'date_column': 'trade_date',
            'symbol_column': 'ts_code',
            'description': f'{data_type}数据',
            'schema': {}
        })
    
    def get_date_column(self, data_type: str) -> str:
        """获取日期列名"""
        config = self.get_config(data_type)
        return config.get('date_column', 'trade_date')
    
    def get_symbol_column(self, data_type: str) -> str:
        """获取标的代码列名"""
        config = self.get_config(data_type)
        return config.get('symbol_column', 'ts_code')
    
    def get_schema(self, data_type: str) -> Dict[str, Any]:
        """获取数据类型的schema定义"""
        config = self.get_config(data_type)
        return config.get('schema', {})
    
    def get_description(self, data_type: str) -> str:
        """获取数据类型的描述"""
        config = self.get_config(data_type)
        return config.get('description', f'{data_type}数据')
    
    def list_all_types(self) -> Dict[str, str]:
        """列出所有数据类型及其描述"""
        result = {}
        for data_type in self.supported_types:
            result[data_type] = self.get_description(data_type)
        return result

# 全局schema管理器实例
schema_manager = SchemaManager()

# 便捷函数
def get_supported_data_types() -> List[str]:
    """获取所有支持的数据类型"""
    return schema_manager.get_supported_types()

def is_data_type_supported(data_type: str) -> bool:
    """检查数据类型是否支持"""
    return schema_manager.is_supported(data_type)

def get_data_type_path(data_type: str) -> str:
    """获取数据类型的MinIO路径"""
    return schema_manager.get_path_prefix(data_type)

def get_data_type_config(data_type: str) -> Dict[str, Any]:
    """获取数据类型的完整配置"""
    return schema_manager.get_config(data_type)