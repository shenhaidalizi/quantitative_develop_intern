#!/bin/bash
# 初始化设置脚本

set -e

echo "🚀 初始化live_monitor项目..."

# 创建必要的目录
echo "📁 创建目录结构..."
mkdir -p shared/{data/{test_result,index_data},logs/{analyzer,monitor},statistic_data}
mkdir -p backups

# 设置权限
echo "🔐 设置目录权限..."
chmod -R 755 shared
chmod -R 755 scripts

# 检查Docker和Docker Compose
echo "🐳 检查Docker环境..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

echo "✅ Docker环境检查通过"

# 创建.env文件（如果不存在）
if [ ! -f .env ]; then
    echo "📝 创建.env配置文件..."
    cat > .env << EOF
# Monitor Service
PORT=8006
NODE_ENV=production

# Analyzer Service  
DATE_INTERVAL=15
NUM_PROCESSES=7
ON_SERVER=true

# Redis
USE_REDIS=true
REDIS_HOST=redis
REDIS_PORT=6379

# Data paths (容器内路径)
STOCK_FOLDER=/app/data/test_result
INDEX_FOLDER=/app/data/index_data
EOF
    echo "✅ .env文件已创建，请根据需要修改配置"
else
    echo "✅ .env文件已存在"
fi

echo ""
echo "✅ 初始化完成！"
echo ""
echo "下一步操作："
echo "1. 编辑 .env 文件调整配置"
echo "2. 运行 'make build' 构建镜像"
echo "3. 运行 'make up' 启动服务"

