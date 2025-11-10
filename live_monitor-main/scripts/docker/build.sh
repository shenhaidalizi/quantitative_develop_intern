#!/bin/bash
# Docker镜像构建脚本

set -e

echo "🔨 开始构建Docker镜像..."

# 构建analyzer镜像
echo "📦 构建analyzer服务..."
docker build -t stock-analyzer:latest ./services/analyzer

# 构建monitor镜像
echo "📦 构建monitor服务..."
docker build -t stock-monitor:latest ./services/monitor

echo "✅ 所有镜像构建完成!"
docker images | grep -E "stock-(analyzer|monitor)"

