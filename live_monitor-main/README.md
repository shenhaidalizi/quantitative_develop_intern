# 🚀 Live Monitor - 股票实时监控系统

基于微服务架构的股票分钟级数据分析和实时监控系统，提供数据处理、统计分析和Web可视化界面。

> 自 v2.1.0 起：Makefile 仅保留默认 `docker-compose.yml` 工作流，已移除共享/独立/自定义 compose 目标（如 `up-shared`、`up-standalone`）。如需特殊部署，请直接使用 `docker-compose -f <your-file>.yml`。

## 📁 项目结构

```
live_monitor/                    # Monorepo根目录
├── services/                    # 微服务目录
│   ├── analyzer/               # Python数据分析服务
│   │   ├── core/               # 核心处理逻辑
│   │   ├── scripts/            # 运维脚本
│   │   ├── tests/              # 单元测试
│   │   ├── benchmarks/         # 性能测试
│   │   ├── Dockerfile          # 镜像构建
│   │   └── requirements.txt    # Python依赖
│   │
│   └── monitor/                # Node.js监控服务
│       ├── src/                # 源代码
│       │   ├── config/         # 配置管理
│       │   ├── services/       # 业务服务
│       │   ├── routes/         # API路由
│       │   ├── middlewares/    # 中间件
│       │   └── utils/          # 工具函数
│       ├── Dockerfile          # 镜像构建
│       └── package.json        # Node依赖
│
├── shared/                     # 共享资源
│   ├── data/                   # 数据文件
│   │   ├── test_result/       # 股票数据
│   │   └── index_data/        # 股指数据
│   ├── logs/                   # 日志文件
│   ├── statistic_data/        # 统计数据
│   └── config/                 # 共享配置
│
├── scripts/                    # 项目级脚本
│   ├── docker/                 # Docker相关
│   ├── init/                   # 初始化脚本
│   └── maintenance/            # 维护脚本
│
├── docker-compose.yml          # Docker编排配置
├── Makefile                    # 快捷命令
└── README.md                   # 项目文档
```

## ✨ 核心特性

### Analyzer服务（Python）
- 📊 分钟级股票数据处理
- 📈 多时间窗口滚动统计（1/5/10/30分钟）
- 🎯 Z-Score标准化计算
- 🔄 实时数据获取和处理
- 💾 数据预处理和缓存

### Monitor服务（Node.js）
- 🌐 现代化Web可视化界面
- 📡 实时数据监控和展示
- 🔍 数据搜索、筛选、排序
- 💾 Redis缓存支持
- 📦 Gzip压缩传输
- 🔗 股吧快速跳转

### 基础设施
- 🐳 Docker容器化部署
- 🔄 自动健康检查
- 📝 统一日志管理
- 🛡️ 优雅关闭处理

## 🚀 快速开始

### 前置要求
- Docker 20.10+
- Docker Compose 1.29+
- （可选）Make工具

### 一键启动

```bash
# 1. 初始化项目
bash scripts/init/setup.sh

# 2. 编辑配置（可选）
vi .env

# 3. 构建并启动所有服务（推荐）
make build && make up

# 或使用 docker-compose 直接操作
docker-compose build --parallel
docker-compose up -d
```

### 访问服务

- **Web界面**: http://localhost:8006
- **API文档**: http://localhost:8006/api/status
- **健康检查**: `make status`

## 📋 常用命令

```bash
# === 服务管理 ===
make build           # 构建所有镜像
make up              # 启动所有服务
make down            # 停止所有服务
make restart         # 重启所有服务
make status          # 查看服务状态

# === 日志查看 ===
make logs            # 查看所有日志
make logs-analyzer   # 查看analyzer日志
make logs-monitor    # 查看monitor日志

# === 开发调试 ===
make shell-analyzer  # 进入analyzer容器
make shell-monitor   # 进入monitor容器
make test           # 运行所有测试

# === 维护清理 ===
make clean          # 清理容器和数据卷
make clean-logs     # 清理日志文件
```

完整命令列表：`make help`

## ⚙️ 配置说明

### 环境变量（.env文件）

```env
# Monitor服务
PORT=8006                        # Web服务端口
NODE_ENV=production              # 运行环境

# Analyzer服务
DATE_INTERVAL=15                 # 数据更新间隔（分钟）
NUM_PROCESSES=7                  # 处理进程数
ON_SERVER=true                   # 服务器模式

# Redis缓存
USE_REDIS=true                   # 启用Redis
REDIS_HOST=redis                 # Redis主机
REDIS_PORT=6379                  # Redis端口

# 数据路径（容器内路径）
STOCK_FOLDER=/app/data/test_result
INDEX_FOLDER=/app/data/index_data
```

## 🏗️ 架构设计

### 服务拓扑

```
┌─────────────────┐
│   Browser/UI    │
└────────┬────────┘
         │ HTTP
         ↓
┌─────────────────┐      ┌─────────────┐
│  Monitor (Node) │◄────►│Redis (Cache)│
└────────┬────────┘      └─────────────┘
         │ File Watch
         ↓
┌─────────────────┐
│ Shared Data Dir │
└────────┬────────┘
         │ Write CSV
         ↓
┌─────────────────┐
│Analyzer (Python)│
└─────────────────┘
```

### 数据流

```
1. Analyzer → 获取实时数据 → 处理分析 → 生成CSV
2. CSV文件 → shared/data/
3. Monitor → 监控文件变化 → 解析CSV → 缓存到Redis
4. Web UI → 请求数据 → Monitor API → 返回JSON
```

## 🧪 测试

```bash
# 单元测试
make test-analyzer   # Python测试
make test-monitor    # Node.js测试

# 性能测试
make benchmark       # 运行性能基准测试

# 集成测试（使用测试数据）
cd services/monitor
npm run test:integration
```

## 📊 性能优化

### 已实现优化
- ✅ Redis缓存（60-80%性能提升）
- ✅ Gzip压缩（70-80%传输量减少）
- ✅ 数据指纹检测（避免无效更新）
- ✅ 增量数据处理
- ✅ 文件监控去抖动

### 建议配置
- 生产环境启用Redis
- 根据数据量调整NUM_PROCESSES
- 定期运行清理脚本

## 🛠️ 运维指南

### 健康检查
```bash
# 检查所有服务
bash scripts/docker/health-check.sh

# 或使用Makefile
make status
```

### 数据备份
```bash
# 备份数据和配置
bash scripts/maintenance/backup.sh

# 备份文件保存在backups/目录
```

### 清理维护
```bash
# 清理旧数据和日志（保留最近7天）
bash scripts/maintenance/cleanup.sh
```

### 日志管理
```bash
# 查看实时日志
docker-compose logs -f

# 查看特定服务
docker-compose logs -f analyzer

# 导出日志
docker-compose logs > logs_export.txt
```

## 🚨 故障排查

### 服务无法启动
```bash
# 1. 检查端口占用
lsof -i :8006

# 2. 查看服务日志
make logs

# 3. 检查Docker状态
docker-compose ps
```

### 数据不更新
```bash
# 1. 检查analyzer服务
make logs-analyzer

# 2. 检查数据目录权限
ls -la shared/data/

# 3. 手动触发重新加载
curl -X POST http://localhost:8006/api/status/reload
```

### Redis连接失败
- Monitor会自动降级到内存缓存
- 检查Redis容器状态：`docker-compose ps redis`
- 查看Redis日志：`make logs-redis`

## 📝 开发指南

### 添加新功能

**Analyzer服务（Python）**
1. 在`services/analyzer/core/`添加核心逻辑
2. 更新`requirements.txt`
3. 编写测试在`tests/`
4. 更新Dockerfile（如需新依赖）

**Monitor服务（Node.js）**
1. 在`src/services/`添加业务逻辑
2. 在`src/routes/`添加API路由
3. 更新`package.json`
4. 编写测试在`tests/`

### 代码规范
- Python遵循PEP 8
- JavaScript使用ESLint
- 添加必要的注释和文档
- 保持函数单一职责

## 🔄 版本历史

### v2.0.0 (2025-10-07)
- ✨ 完全重构为monorepo架构
- ✨ 模块化服务设计
- ✨ Docker完整支持
- ✨ 统一配置管理
- ✨ 改进错误处理和日志

### v1.0.0
- 初始版本

## 📄 许可证

MIT License

## 👥 贡献者

- panwen - 项目维护者

## 📮 联系方式

如有问题或建议，请提交Issue。

---

**提示**: 
- 生产环境推荐使用Docker部署
- 定期运行备份和清理脚本
- 关注日志，及时发现问题


tips:
新的实现写在new_timely_data中，采样每分钟数据进行数据计算，会在data文件夹下生成最近五分钟传给前端的json文件，可以借此查看系统状态和计算信息，如果需要后续调试，可以将debug模式置为True，可以生成每分钟的中间数据，包含采样数据，构造后的df，计算后的z_score等中间文件，对于其中的计算逻辑，rolling_full直接使用数据，其他的rolling数据通过减法和滑动窗口实现,zscore计算公式为（rolling - mean）/ std, 这个程序尚且存在bug，在非交易时间时时间未能正确进行，疑似是print太多导致任务阻塞，所以需要小修一下。另外，股指数据还未接入数据源，但是不需要计算，从amazing_data中获取数据把接口对上就应该可以正常实现，原有逻辑实现在timely_data中，可以初步参考。计算中还有一个中间环节需要注意：涨幅使用的是（现在 - pre_close）/ pre_close，因此数据会因为尚未调整有错误。
可以使用./auto.sh进行快速重建；
generate.py可以简单模拟fake数据
在scripts文件夹下，bootstrap.sh用以导入minio_api, preprocess.cron用来设置定时任务，但尚未能验证其正确性。
后续可以对前端进行优化。