#!/bin/bash
# Docker服务健康检查脚本

set -e

echo "🏥 检查服务健康状态..."

# 检查analyzer服务
echo "检查analyzer服务..."
if docker-compose ps analyzer | grep -q "Up"; then
    echo "✅ Analyzer服务运行正常"
else
    echo "❌ Analyzer服务异常"
    exit 1
fi

# 检查monitor服务
echo "检查monitor服务..."
if docker-compose ps monitor | grep -q "Up"; then
    # 检查HTTP接口
    if curl -f http://localhost:8006/api/status > /dev/null 2>&1; then
        echo "✅ Monitor服务运行正常"
    else
        echo "❌ Monitor服务HTTP接口无响应"
        exit 1
    fi
else
    echo "❌ Monitor服务异常"
    exit 1
fi

# 检查Redis服务
echo "检查Redis服务..."
if docker-compose ps redis | grep -q "Up"; then
    echo "✅ Redis服务运行正常"
else
    echo "⚠️ Redis服务异常（可选服务）"
fi

echo ""
echo "✅ 所有核心服务健康！"

