服务器中有data_fetcher.py, 本地测试是使用 stock_minute_data_test.csv

# 股票分钟级数据分析系统

一个基于Python和Node.js的股票分钟级数据分析和监控系统，提供实时数据处理、统计分析和Web可视化界面。

## 🚀 项目特性

- **分钟级数据处理**：支持股票和股指的分钟级数据预处理和分析
- **滚动窗口分析**：提供1、5、10、30分钟等多时间窗口的滚动统计
- **Z-Score计算**：实时计算成交量的标准化分数，识别异常交易活动
- **实时数据监控**：自动获取和处理实时股票数据
- **Web可视化界面**：提供现代化的Web界面展示数据和分析结果
- **交互式功能**：支持数据排序、搜索、筛选和股吧跳转
- **自动文件管理**：智能管理历史数据文件，避免存储空间溢出

## 📁 项目结构

```
stock_minute_analysis/
├── data/                           # 数据文件夹
│   ├── test_result/               # 实时股票数据输出
│   ├── index_data/                # 实时股指数据输出
│   ├── stock_minute_data_test.csv # 历史股票数据
│   └── index_weight_data.csv      # 股指权重数据
├── statistic_data/                # 统计分析结果
│   └── time_data_YYYY-MM-DD.json # 预处理统计数据
├── test_function/                 # 测试模块
├── preprocess_data.py             # 数据预处理脚本
├── test_timely_data.py           # 实时数据处理脚本
├── index_weight.py               # 股指权重处理
└── README.md
```

## 🛠️ 环境要求

### Python环境
- Python 3.7+
- pandas
- numpy
- tqdm
- requests

### Node.js环境
- Node.js 14.0+
- express
- chokidar
- cors

## 📦 安装依赖

### Python依赖
```bash
pip install pandas numpy tqdm requests
```

### Node.js依赖
```bash
# 初始化npm项目（首次运行）
npm init -y

# 安装依赖
npm install express chokidar cors
```

## 🔧 配置说明

### 1. 预处理配置
在 `preprocess_data.py` 中修改以下配置：

```python
# 配置参数
WINDOW_LENGTH_LIST = [1, 5, 10, 30]  # 滚动窗口长度
TARGET_DATE = '2025-07-01'           # 目标日期  
DATE_INTERVAL = 3                    # 日期间隔

# 路径配置
input_csv_path = "data/stock_minute_data_test.csv"
output_dir = "statistic_data"
```

### 2. 实时数据配置
在 `test_timely_data.py` 中修改以下配置：

```python
# 系统配置
MAX_ROLLING_LENGTH: int = 30         # 缓存数据最大长度
MAX_RESULT_FILES: int = 5           # 结果文件最大数量
UPDATE_INTERVAL: int = 60           # 更新间隔（秒）

# API配置
API_URL = "http://dataapi.trader.com/live/cn/all"  # 实时数据API

# 路径配置
previous_data_path = "statistic_data/time_data_2025-07-01.json"  # 预处理数据路径
save_data_path = "data/test_result"     # 股票数据保存路径
index_data_path = "data/index_data"     # 股指数据保存路径
index_weight_data_path = "data/index_weight_data.csv"  # 股指权重数据
```

### 3. Web服务配置
在 `../stock_monitor/server.js` 中修改端口和路径：

```javascript
const PORT = 3002;  // Web服务端口
const STOCK_FOLDER = '/path/to/stock_minute_analysis/data/test_result';
const INDEX_FOLDER = '/path/to/stock_minute_analysis/data/index_data';
```

## 🚦 使用指南

### 第一步：数据预处理
在交易日开盘前完成数据预处理（建议在前一天完成）：

```bash
python preprocess_data.py
```

**功能说明**：
- 读取历史股票分钟数据
- 计算多时间窗口的滚动统计
- 生成标准化的统计数据文件
- 输出：`statistic_data/time_data_{TARGET_DATE}.json`

### 第二步：实时数据监控
在交易时间启动实时数据处理：

```bash
python test_timely_data.py
```

**功能说明**：
- 自动运行到交易结束时间（15:00）
- 每分钟获取实时股票和股指数据
- 计算实时Z-Score指标
- 生成CSV格式的分析结果
- 自动管理历史文件

### 第三步：Web可视化
启动Web监控界面：

```bash
cd ../stock_monitor
node server.js
```

然后在浏览器中打开：`http://localhost:3002`

**Web界面功能**：
- 📊 实时数据展示（股票和股指）
- 🔍 搜索和过滤功能
- 📈 多指标排序
- 🔗 双击股票代码跳转股吧
- ⏱️ 自动数据刷新（5秒间隔）
- 📱 响应式设计，支持移动端

## 📊 数据指标说明

### 股票数据指标
- **代码/名称**：股票代码和名称
- **价格**：当前股价
- **涨跌幅**：当日涨跌幅百分比
- **成交量**：当前成交量
- **Z-Score**：1/5/10/30分钟成交量标准化分数
- **历史涨跌幅**：5/30分钟历史涨跌幅

### 股指数据指标
- **代码**：股指代码
- **涨跌幅**：指数涨跌幅
- **成交量**：指数成交量
- **Z-Score**：多时间窗口标准化分数

### Z-Score解释
- **> 2**：成交量异常偏高（红色高亮）
- **< -2**：成交量异常偏低（绿色高亮）
- **[-2, 2]**：成交量正常范围

## 🔍 故障排除

### 常见问题

1. **数据文件未找到**
   ```
   确保数据文件路径正确，检查文件是否存在
   ```

2. **Web界面无法访问**
   ```bash
   # 检查端口是否被占用
   lsof -i :3002
   
   # 杀死占用端口的进程
   bash kill_port.sh
   ```

3. **实时数据获取失败**
   ```
   检查API_URL是否可访问
   检查网络连接
   检查API密钥或权限设置
   ```

4. **内存使用过高**
   ```
   调整MAX_ROLLING_LENGTH参数
   定期清理历史数据文件
   ```

### 日志检查
- Python脚本的输出会显示详细的处理进度
- Web服务的日志会显示文件监控和API请求状态
- 检查控制台输出了解运行状态
