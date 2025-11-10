# MinIO API

一个用于从MinIO对象存储中高效读取多种金融数据的Python库，支持股票、指数、资金流等多种数据类型。

## 功能特性

- 🚀 **高性能数据读取**：直接从MinIO读取parquet文件，绕过传统API
- 📊 **多数据类型支持**：支持股票、指数、基础信息、资金流向等多种数据
- 🔧 **复权处理**：智能处理前复权、后复权和不复权数据
- 📅 **智能查询**：自动处理跨月份数据查询和合并
- 🛡️ **安全连接**：支持SSL/TLS和非SSL连接
- 🎯 **简洁API**：所有方法直接返回DataFrame，简单易用

## 安装

```bash
# 进入项目目录
cd /minio_api

# 安装依赖
pip install -e .
```

## 配置要求

### 1. 创建.env文件

**必须**在项目根目录创建`.env`文件，包含以下MinIO连接配置：

```bash
# MinIO连接配置
MINIO_ENDPOINT=192.168.12.16:30900
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_SECURE=false
MINIO_BUCKET_NAME=your_bucket_name
```

### 2. 配置说明

| 参数 | 描述 | 示例 | 必需 |
|------|------|------|------|
| `MINIO_ENDPOINT` | MinIO服务器地址 | `192.168.12.16:30900` | ✅ |
| `MINIO_ACCESS_KEY` | 访问密钥 | `minioadmin` | ✅ |
| `MINIO_SECRET_KEY` | 秘密密钥 | `minioadmin` | ✅ |
| `MINIO_SECURE` | 是否使用HTTPS | `true/false` | ✅ |
| `MINIO_BUCKET_NAME` | 数据桶名称 | `bucket` | ✅ |

⚠️ **重要提醒**：
- `.env`文件包含敏感信息，请勿提交到版本控制系统
- 确保MinIO服务器可访问且凭据正确
- `MINIO_ENDPOINT`支持完整URL格式（如`http://host:port`）或简单格式（如`host:port`）

## 快速开始

### 基本使用 - 多数据类型支持

```python
from minio_api import MinIOStockDataClient

# 初始化客户端（自动读取.env配置）
client = MinIOStockDataClient()

# 获取不同类型的数据 - 直接返回DataFrame
cnstock_data = client.get_data("CNSTOCK", "20240101", "20241231")
cnindex_data = client.get_data("CNINDEX", "20240101", "20241231") 
moneyflow_data = client.get_data("CNSTOCK_MONEYFLOW", "20240101", "20241231")

print(f"股票数据行数: {len(cnstock_data)}")
print(f"指数数据行数: {len(cnindex_data)}")
print(f"资金流数据行数: {len(moneyflow_data)}")
```

### 复权处理

```python
# 获取不同复权类型的股票数据
bfq_data = client.get_data("CNSTOCK", "20240101", "20241231", fq_type="bfq")  # 不复权
qfq_data = client.get_data("CNSTOCK", "20240101", "20241231", fq_type="qfq")  # 前复权  
hfq_data = client.get_data("CNSTOCK", "20240101", "20241231", fq_type="hfq")  # 后复权

# 兼容性方法
stock_data = client.get_stock_data_fast(
    start_date="20240101",
    end_date="20241231", 
    symbols="all",
    fq_type="qfq"
)
```

### 便捷函数

```python
# 使用便捷函数快速获取数据
from minio_api import (
    get_cnstock_data, 
    get_cnstock_basic_data, 
    get_cnstock_moneyflow_data,
    get_cnindex_data
)

# 获取股票数据（支持复权）
df1 = get_cnstock_data("20150101", "20241231", fq_type="qfq")

# 获取基础信息数据
df2 = get_cnstock_basic_data("20150101", "20241231")

# 获取资金流向数据
df3 = get_cnstock_moneyflow_data("20150101", "20241231")

# 获取指数数据
df4 = get_cnindex_data("20150101", "20241231")
```

### 数据类型查询

```python
# 查看支持的数据类型
from minio_api import list_supported_data_types
supported_types = list_supported_data_types()
print("支持的数据类型:", supported_types)

# 获取数据类型详细信息
from minio_api import get_data_type_info
info = get_data_type_info("CNSTOCK")
print("CNSTOCK信息:", info)

# 查看可用数据
available_data = client.list_available_data()
print("可用数据概览:", available_data)
```

### 连接测试

```python
# 测试MinIO连接
from minio_api import test_minio_connection
if test_minio_connection():
    print("MinIO连接成功！")
else:
    print("MinIO连接失败，请检查配置")
```

## 支持的数据类型

| 数据类型 | 描述 | 复权支持 |
|----------|------|----------|
| `CNSTOCK` | 中国股票日线数据 | ✅ bfq/qfq/hfq |
| `CNSTOCK_ADJ` | 中国股票复权因子 | ❌ |
| `CNSTOCK_BASIC` | 中国股票基础信息 | ❌ |
| `CNINDEX` | 中国指数数据 | ❌ |
| `CNSTOCK_MONEYFLOW` | 中国股票资金流向数据 | ❌ |
| `SWINDEX` | 申万指数数据 | ❌ |
| `CNFUND` | 中国基金数据 | ❌ |
| `CNFUND_ADJ` | 中国基金调整因子 | ❌ |
| `CNFUT` | 中国期货数据 | ❌ |
| `CNSTOCK_LIMIT` | A股每日涨跌停价格 | ❌ |
| `CNSTOCK_MARGIN_DETAIL` | 融资融券交易明细 | ❌ |
| `CIINDEX` | 中信指数 | ❌ |
| `THSINDEX` | 同花顺概念指数 | ❌ |
| `GLOBALINDEX` | 全球重要指数 | ❌ |
| `CNINDEX_BASIC` | A股指数基本信息 | ❌ |
| `CNMARKET_STATS` | 市场整体统计 | ❌ |
| `CNFINA_INDICATOR` | A股上市公司财务指标数据 | ❌ |
| `OPT_DAILY` | 期权日线数据 | ❌ |

## API参考

### MinIOStockDataClient

#### `get_data()`

```python
def get_data(
    data_type: str = "CNSTOCK",
    start_date: str = "20200101",
    end_date: str = "20250101", 
    symbols: Union[str, List[str]] = "all",
    fq_type: str = "bfq"
) -> pd.DataFrame
```

**参数：**
- `data_type`: 数据类型，支持上表中的所有类型
- `start_date`: 开始日期，格式YYYYMMDD
- `end_date`: 结束日期，格式YYYYMMDD  
- `symbols`: 标的代码，"all"表示所有标的，或传入代码列表
- `fq_type`: 复权类型（bfq/qfq/hfq），仅对股票数据有效

**返回：**
- `pd.DataFrame`: 数据

#### `get_stock_data_fast()` (兼容性方法)

```python
def get_stock_data_fast(
    start_date: str = "20200101",
    end_date: str = "20250101", 
    symbols: Union[str, List[str]] = "all",
    fq_type: str = "qfq"
) -> pd.DataFrame
```

**参数：**
- `start_date`: 开始日期，格式YYYYMMDD
- `end_date`: 结束日期，格式YYYYMMDD  
- `symbols`: 股票代码，"all"表示所有股票，或传入股票代码列表
- `fq_type`: 复权类型（bfq/qfq/hfq）

**返回：**
- `pd.DataFrame`: 股票数据

### 便捷函数

```python
# 股票数据
get_cnstock_data(start_date, end_date, symbols="all", fq_type="bfq", config=None)

# 股票基础信息
get_cnstock_basic_data(start_date, end_date, symbols="all", config=None)

# 资金流向数据
get_cnstock_moneyflow_data(start_date, end_date, symbols="all", config=None)

# 指数数据
get_cnindex_data(start_date, end_date, symbols="all", config=None)

# 调整因子数据
get_cnstock_adj_data(start_date, end_date, symbols="all", config=None)
```

### 工具函数

```python
# 列出支持的数据类型
list_supported_data_types() -> List[str]

# 获取数据类型信息
get_data_type_info(data_type: str) -> dict

# 测试连接
test_minio_connection(config=None) -> bool

# 获取可用数据概览
get_available_data_summary(config=None) -> dict
```

## 复权说明

### 复权类型

- **bfq (不复权)**：原始价格，未经任何调整
- **qfq (前复权)**：以最新价格为基准，历史价格向前调整
- **hfq (后复权)**：以最早价格为基准，后续价格向后调整

### 复权实现

1. 获取原始股票数据 (CNSTOCK)
2. 获取调整因子数据 (CNSTOCK_ADJ) 
3. 使用 `merge_asof` 匹配调整因子
4. 根据复权类型计算调整比例
5. 价格列乘以调整因子，成交量除以调整因子

## 错误处理

```python
try:
    df = client.get_data("CNSTOCK", "20240101", "20241231")
except ValueError as e:
    print(f"参数错误: {e}")
except Exception as e:
    print(f"数据获取失败: {e}")
```

## 性能优化建议

1. **合理设置日期范围**：避免查询过大的时间跨度
2. **指定具体标的**：避免使用 `symbols="all"` 除非确实需要
3. **复权数据缓存**：对于同样的复权数据，可以考虑缓存结果
4. **并行查询**：对于多个独立查询，可以使用多线程并行处理

## 项目结构

```
minio_api/
├── src/minio_api/
│   ├── __init__.py          # 主要导出
│   ├── client.py            # 核心客户端
│   ├── config.py            # 配置管理
│   ├── schemas.py           # 数据类型定义
│   ├── utils.py             # 便捷函数
│   └── adj_utils.py         # 复权工具
├── debug/                   # 测试脚本
├── pyproject.toml          # 项目配置
└── README.md               # 本文件
```

## 版本历史

- **v1.1.0**: 多数据类型支持，复权处理，API简化
- **v1.0.0**: 基础MinIO数据读取功能
```