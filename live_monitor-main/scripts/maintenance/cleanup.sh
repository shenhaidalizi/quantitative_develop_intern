#!/bin/bash
# 清理脚本 - 清理旧数据和日志

set -e

echo "🧹 开始清理..."

# 清理旧的数据文件（保留最近7天）
echo "📁 清理旧数据文件..."
find shared/data/test_result -name "*.csv" -mtime +7 -delete 2>/dev/null || true
find shared/data/index_data -name "*.csv" -mtime +7 -delete 2>/dev/null || true

# 清理旧的日志文件（保留最近30天）
echo "📝 清理旧日志..."
find shared/logs -name "*.log" -mtime +30 -delete 2>/dev/null || true

# 清理Docker未使用的资源
echo "🐳 清理Docker资源..."
docker system prune -f --volumes

echo "✅ 清理完成！"

