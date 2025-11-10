# Redis共享方案指南

> 自 v2.1.0 起：项目 `Makefile` 仅保留默认 `docker-compose.yml` 工作流。本文档作为共享 Redis 的参考方案，相关示例需通过 `docker-compose -f <file>.yml` 或自定义 override 文件实现，不再内置 `up-shared` / `up-standalone` 等快捷目标。

## 问题背景

多个项目都需要Redis，但不想启动多个Redis实例浪费资源。

## 📊 方案对比

| 方案 | Redis位置 | 配置难度 | 资源占用 | 隔离性 | 推荐场景 |
|------|-----------|----------|----------|--------|----------|
| **原始配置** | 每项目独立 | ⭐ 简单 | 高 | ⭐⭐⭐ | 生产环境 |
| **方案1: 复用Redis** | platform_api | ⭐⭐ 中等 | 低 | ⭐⭐ | 开发环境 ✅ |
| **方案2: 宿主机Redis** | 宿主机 | ⭐⭐⭐ 复杂 | 最低 | ⭐ | 本地开发 |
| **方案3: 独立共享Redis** | 独立容器 | ⭐⭐ 中等 | 低 | ⭐⭐⭐ | 推荐生产 ⭐ |

---

## 方案1: 复用platform_api的Redis（推荐开发环境）

### 优点
✅ 节省资源（只运行一个Redis）  
✅ 配置简单  
✅ 适合开发和测试  

### 缺点
⚠️ 两个项目耦合  
⚠️ platform_api停止会影响live_monitor  

### 使用步骤

#### 1. 确保platform_api的Redis正在运行
```bash
cd /home/ubuntu/dev-TradeNew/infra/platform_api_dev
docker-compose up -d redis

# 验证Redis运行
docker ps | grep platform_api_8004_redis
```

#### 2. 使用共享配置启动live_monitor
```bash
cd /home/ubuntu/TradeNew/live/live_monitor

# 使用共享Redis配置（手动指定 compose 文件）
docker-compose -f docker-compose.shared-redis.yml up -d
```

#### 3. 验证连接
```bash
# 进入monitor容器
docker exec -it stock-monitor sh

# 测试Redis连接
wget -q -O- http://localhost:8006/api/status

# 检查Redis
apk add redis
redis-cli -h platform_api_8004_redis -n 1 ping
# 应该返回: PONG
```

### 配置说明

```yaml
# 关键配置点
environment:
  - REDIS_HOST=platform_api_8004_redis  # ← 使用platform_api的Redis容器名
  - REDIS_PORT=6379                      # ← 容器内部端口
  - REDIS_DB=1                           # ← 使用DB1，避免冲突

networks:
  platform_api_8004_network:            # ← 加入platform_api的网络
    external: true
```

### Redis数据库分配

| 项目 | Redis DB | 用途 |
|------|----------|------|
| platform_api | DB 0 | Celery任务队列 |
| live_monitor | DB 1 | 股票数据缓存 |
| 预留 | DB 2-15 | 其他项目 |

---

## 方案2: 使用宿主机Redis

### 优点
✅ 完全解耦，项目独立  
✅ 最节省资源  
✅ 统一管理  

### 缺点
⚠️ 需要在宿主机安装Redis  
⚠️ 容器访问宿主机略复杂  

### 使用步骤

#### 1. 在宿主机安装Redis（如未安装）
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# 启动Redis
sudo systemctl start redis
sudo systemctl enable redis

# 验证
redis-cli ping
# 应该返回: PONG
```

#### 2. 修改Redis配置允许Docker访问
```bash
sudo vim /etc/redis/redis.conf

# 找到并修改（注意：生产环境请设置密码）
bind 0.0.0.0  # 或 bind 127.0.0.1 ::1 172.17.0.1

# 重启Redis
sudo systemctl restart redis
```

#### 3. 使用standalone配置
```bash
cd /home/ubuntu/TradeNew/live/live_monitor

# 创建.env配置
cat >> .env << EOF
USE_REDIS=true
REDIS_HOST=host.docker.internal  # Docker访问宿主机
REDIS_PORT=6379
REDIS_DB=2
EOF

# 启动服务
docker-compose -f docker-compose.standalone.yml up -d
```

---

## 方案3: 创建独立共享Redis服务（推荐生产）

### 优点
✅ 专业的架构设计  
✅ 服务解耦  
✅ 易于维护和监控  
✅ 可配置持久化和高可用  

### 使用步骤

#### 1. 创建共享Redis服务
```bash
# 创建共享Redis目录
mkdir -p /home/ubuntu/shared-services

cat > /home/ubuntu/shared-services/docker-compose.yml << 'EOF'
version: '3.8'

services:
  redis:
    image: hub.zoyutech.com/library/redis:8
    container_name: shared-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes  # 启用持久化
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - shared-network

volumes:
  redis-data:
    name: shared_redis_data

networks:
  shared-network:
    name: shared_network
    driver: bridge
EOF

# 启动共享Redis
cd /home/ubuntu/shared-services
docker-compose up -d
```

#### 2. 修改各项目连接到共享Redis

**platform_api_dev:**
```yaml
# docker-compose.yml
services:
  api:
    environment:
      REDIS_URL: redis://shared-redis:6379/0
    networks:
      - shared-network

networks:
  shared-network:
    external: true
```

**live_monitor:**
```yaml
# docker-compose.yml
services:
  monitor:
    environment:
      REDIS_HOST: shared-redis
      REDIS_DB: 1
    networks:
      - shared-network

networks:
  shared-network:
    external: true
```

---

## 🚀 快速决策指南

### 选择方案1（复用Redis）如果：
- ✅ 你在开发环境
- ✅ platform_api项目始终运行
- ✅ 想要最简单的配置

### 选择方案2（宿主机Redis）如果：
- ✅ 你有宿主机管理权限
- ✅ 想要最灵活的配置
- ✅ 项目数量多

### 选择方案3（独立共享Redis）如果：
- ✅ 你在生产环境
- ✅ 需要专业的架构
- ✅ 需要Redis持久化和监控

---

## 📝 关于 Makefile 快捷命令

自 v2.1.0 起，仓库不再内置 `up-shared` / `up-standalone` 等目标。如需保留类似快捷方式，请在本地自定义 Makefile 或脚本，内部调用：

```bash
docker-compose -f docker-compose.shared-redis.yml up -d
docker-compose -f docker-compose.standalone.yml up -d
```

---

## 🔍 故障排查

### 连接失败

**问题**: `ECONNREFUSED` 或 `connection refused`

**检查清单**:
```bash
# 1. 检查Redis是否运行
docker ps | grep redis

# 2. 检查网络连接
docker network ls
docker network inspect platform_api_8004_network

# 3. 测试连接
docker exec -it stock-monitor sh
ping platform_api_8004_redis  # 能ping通吗？
```

### 数据冲突

**问题**: 两个项目的数据互相干扰

**解决**: 确保使用不同的Redis DB
```bash
# 检查当前使用的DB
redis-cli -h platform_api_8004_redis
> SELECT 1
> KEYS *
```

---

## 📊 性能对比

| 配置 | 内存占用 | 启动时间 | 网络延迟 |
|------|----------|----------|----------|
| 独立Redis×2 | ~200MB | 3-5秒 | 最低 |
| 共享Redis（方案1） | ~100MB | 2-3秒 | 低 |
| 宿主机Redis | ~80MB | 1秒 | 最低 |

---

## 💡 建议

**开发环境**: 使用**方案1**（复用Redis）

**生产环境**: 使用**方案3**（独立共享Redis）+ Redis Sentinel高可用

**个人本地**: 使用**方案2**（宿主机Redis）

---

有问题随时查阅本文档！

