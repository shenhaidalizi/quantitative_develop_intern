# 数据路径统一说明

## 📂 统一后的路径结构

> 自 v2.1.0 起：Makefile 仅保留默认 `docker-compose.yml` 工作流。若需使用额外的 compose 文件（如共享/独立 Redis 的变体），请使用 `docker-compose -f <file>.yml` 手动指定。

### 容器内路径（统一使用 `/app/data`）

```
/app/
├── data/                          # 🎯 统一数据根目录
│   ├── index_weight_data.csv     # 指数权重数据
│   ├── test_result/               # analyzer 生成，monitor 读取
│   │   └── test_HHMMSS_idx*.csv
│   ├── index_data/                # analyzer 生成，monitor 读取
│   │   └── HH:MM:SS.csv
│   ├── test_data/                 # 测试数据（可选）
│   └── test_data_dev/             # 开发测试数据
│       ├── test_result/
│       └── index_data/
├── statistic_data/                # analyzer 的统计数据
│   └── time_data_*.parquet
└── logs/                          # 日志目录
    ├── analyzer/
    └── monitor/
```

### 宿主机路径（示例）

```
<PROJECT_ROOT>/
└── shared/
    ├── data/                      → 挂载到 /app/data
    ├── statistic_data/            → 挂载到 /app/statistic_data
    └── logs/                      → 挂载到 /app/logs
```

## 🔄 数据流向

```
Analyzer (生成)              Monitor (使用)
     ↓                            ↓
/app/data/test_result/*.csv  ←   文件监控 + 解析
/app/data/index_data/*.csv   ←   文件监控 + 解析
     ↓                            ↓
共享挂载: ./shared/data:/app/data
```

## ⚙️ 配置方式

### Analyzer（示例：自定义 compose 文件，需手动 `-f` 指定）

```yaml
environment:
  - DATA_ROOT=/app              # 设置数据根目录

volumes:
  - ./shared/data:/app/data     # 数据目录
  - ./shared/statistic_data:/app/statistic_data
  - ./shared/logs/analyzer:/app/logs
```

### Monitor（示例：自定义 compose 文件，需手动 `-f` 指定）

```yaml
environment:
  - STOCK_FOLDER=/app/data/test_result
  - INDEX_FOLDER=/app/data/index_data

volumes:
  - ./shared/data:/app/data:ro  # 只读挂载
  - ./shared/logs/monitor:/app/logs
```

## ✅ 验证方式

### 1. 检查容器内路径

```bash
# 进入 analyzer 容器
docker exec -it stock-analyzer ls -la /app/data/

# 进入 monitor 容器
docker exec -it stock-monitor ls -la /app/data/
```

### 2. 检查宿主机路径

```bash
ls -la shared/data/
```

### 3. 验证数据共享

```bash
# 在 analyzer 容器中创建测试文件
docker exec stock-analyzer touch /app/data/test.txt

# 在宿主机上查看
ls shared/data/test.txt

# 在 monitor 容器中查看
docker exec stock-monitor ls /app/data/test.txt
```

## 🎯 优势

1. **路径统一**：两个服务都使用 `/app/data`，易于理解
2. **配置灵活**：通过 `DATA_ROOT` 环境变量控制
3. **数据共享**：analyzer 生成的数据自动被 monitor 读取
4. **权限清晰**：monitor 使用只读挂载（`:ro`）保护数据

## 📝 注意事项

1. `index_data` 目录必须存在，否则 monitor 会警告
2. analyzer 在非开盘时间需要历史 parquet 文件才能启动
3. 所有路径都相对于 `DATA_ROOT` 环境变量
