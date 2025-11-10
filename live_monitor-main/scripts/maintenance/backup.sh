#!/bin/bash
# 数据备份脚本

set -e

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="live_monitor_backup_${DATE}"

echo "💾 开始备份..."

# 创建备份目录
mkdir -p ${BACKUP_DIR}

# 备份配置文件
echo "📋 备份配置文件..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_config.tar.gz \
    .env docker-compose.yml Makefile \
    services/*/Dockerfile \
    services/*/.env 2>/dev/null || true

# 备份数据文件
echo "📊 备份数据文件..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_data.tar.gz \
    shared/data \
    shared/statistic_data 2>/dev/null || true

# 备份日志
echo "📝 备份日志..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}_logs.tar.gz \
    shared/logs 2>/dev/null || true

echo "✅ 备份完成！"
echo "备份文件保存在: ${BACKUP_DIR}/"
ls -lh ${BACKUP_DIR}/${BACKUP_NAME}_*

