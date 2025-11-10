.PHONY: help build up down restart logs clean test status

help: ## 显示帮助信息
	@echo "股票分析监控系统 - Monorepo"
	@echo "================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========== Docker相关 ==========

build: ## 构建所有服务
	@echo "🔨 构建所有服务..."
	docker-compose build --parallel

up: ## 启动所有服务（包含独立Redis）
	@echo "🚀 启动所有服务..."
	docker-compose up -d 
	docker-compose up -d 
	@sleep 2
	@make status
	@echo ""
	@echo "✅ 服务已启动"
	@echo "📊 Web界面: http://localhost:8006"



# 文件: Makefile（根目录）可选增加便捷命令
up-preprocess: ## 启动定时预处理
	@docker-compose up -d preprocess

logs-preprocess: ## 查看预处理日志
	@docker-compose logs -f preprocess

# 文件: Makefile（根目录）可选增加便捷命令
up-preprocess: ## 启动定时预处理
	@docker-compose up -d preprocess

logs-preprocess: ## 查看预处理日志
	@docker-compose logs -f preprocess

down: ## 停止所有服务
	@echo "🛑 停止所有服务..."
	docker-compose down



restart: ## 重启所有服务
	@echo "🔄 重启所有服务..."
	docker-compose restart
	@make status

# ========== 日志相关 ==========

logs: ## 查看所有日志
	docker-compose logs -f

logs-analyzer: ## 查看Analyzer日志
	docker-compose logs -f analyzer

logs-monitor: ## 查看Monitor日志
	docker-compose logs -f monitor

logs-redis: ## 查看Redis日志
	docker-compose logs -f redis

# ========== 状态和调试 ==========

status: ## 查看服务状态
	@echo "📊 服务状态："
	@docker-compose ps

ps: status ## 同 status

shell-analyzer: ## 进入Analyzer容器
	docker-compose exec analyzer /bin/bash

shell-monitor: ## 进入Monitor容器
	docker-compose exec monitor /bin/sh

shell-redis: ## 进入Redis容器
	docker-compose exec redis redis-cli

test-redis: ## 测试Redis连接
	@echo "🔍 测试Redis连接..."
	@docker exec stock-monitor sh -c 'wget -q -O- http://localhost:8006/api/status | grep redis' || echo "❌ 连接失败"

# ========== 测试相关 ==========

test: ## 运行所有测试
	@echo "🧪 运行Analyzer测试..."
	cd services/analyzer && python -m pytest tests/ -v
	@echo ""
	@echo "🧪 运行Monitor测试..."
	cd services/monitor && npm test

test-analyzer: ## 运行Analyzer测试
	cd services/analyzer && python -m pytest tests/ -v

test-monitor: ## 运行Monitor测试
	cd services/monitor && npm test

benchmark: ## 运行性能基准测试
	cd services/analyzer && python benchmark_performance.py

# ========== 清理相关 ==========

clean: ## 清理容器和数据卷
	@echo "🧹 清理容器和数据..."
	docker-compose down -v
	docker system prune -f

clean-data: ## 清理数据文件
	@echo "🗑️  清理数据文件..."
	rm -rf services/analyzer/data/test_result/*
	rm -rf services/analyzer/data/index_data/*
	rm -rf services/analyzer/statistic_data/*.parquet
	@echo "✅ 数据已清理"

clean-logs: ## 清理日志文件
	@echo "🗑️  清理日志..."
	rm -rf shared/logs/*
	@echo "✅ 日志已清理"

# ========== Git相关 ==========

git-status: ## 检查Git状态
	@echo "📋 Git状态："
	@git status -s

git-cleanup: ## 清理子目录的Git仓库
	@bash cleanup_git.sh

# ========== 开发相关 ==========

prod: ## 启动生产环境
	docker-compose up -d --build

install: ## 安装依赖
	@echo "📦 安装Python依赖..."
	cd services/analyzer && pip install -r requirements.txt
	@echo "📦 安装Node.js依赖..."
	cd services/monitor && npm install

# ========== 部署相关 ==========
