# 变更日志

本文档记录项目的所有重要变更。

## [2.1.0] - 2025-10-31

### 🔄 变更
- 精简 Makefile：仅保留默认 `docker-compose.yml` 工作流
- 移除以下目标：`up-shared`、`up-standalone`、`down-shared`、`down-standalone`、`status-shared`、`dev`、`deploy`

### 📝 文档
- 重写根目录 README：统一到默认 docker-compose 工作流
- 更新 `docs/REDIS_SHARING.md`：标注不再内置共享/独立模式，提供手动示例

### ⚠️ 迁移
- 使用基础命令：`make build && make up`、`make down`、`make status`
- 如需共享/独立 Redis，请直接使用 `docker-compose -f <file>.yml`

---

## [2.0.0] - 2025-10-07

### ✨ 新增
- 完全重构为Monorepo架构
- Monitor服务模块化重构（src/目录结构）
- Analyzer服务Docker支持
- 统一的scripts管理系统
- 共享数据目录结构（shared/）
- 完整的Docker Compose编排
- Makefile快捷命令
- 健康检查和监控脚本
- 数据备份和清理脚本

### 🔄 变更
- Monitor服务拆分为services/routes/middlewares/utils层
- Analyzer服务重新组织目录结构（core/tests/benchmarks）
- 配置集中管理（config目录）
- README文档重写（面向Docker部署）

### 🗑️ 删除
- 移除本地部署相关文件（systemd service）
- 删除多余的README文件
- 清理旧的shell脚本重复文件

### 🐛 修复
- 文件路径规范化
- Docker构建优化

### 📝 文档
- 项目根README完全重写
- 各服务README更新
- 添加架构说明和使用指南

---

## [1.0.0] - 2025-07-01

### ✨ 初始版本
- 基础股票数据分析功能
- Web监控界面
- 实时数据处理

