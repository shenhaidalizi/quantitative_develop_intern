# GitLab CI/CD 使用指南

## 📋 概述

本项目使用GitLab CI/CD实现自动化测试、构建和部署。

## 📁 配置文件位置

```
.gitlab-ci.yml         # ✅ 项目根目录（Monorepo主配置）
```

**注意**: services下的子配置已移除，统一由根目录管理。

## 🔄 CI/CD 流程

```
提交代码 → 测试 → 构建镜像 → 部署
   ↓         ↓          ↓          ↓
  Push     Test     Docker    Kubernetes
```

## 🎯 Pipeline 阶段

### 1. Test Stage（测试阶段）

#### test:analyzer
- **触发条件**: `services/analyzer/` 或 `shared/` 目录有变更
- **执行内容**: Python单元测试
- **运行环境**: Python 3.10

#### test:monitor
- **触发条件**: `services/monitor/` 或 `shared/` 目录有变更
- **执行内容**: Node.js测试
- **运行环境**: Node.js 20

### 2. Build Stage（构建阶段）

#### build:analyzer
- **触发条件**: 
  - Git标签（tags）
  - main分支
  - develop分支
- **执行内容**: 构建Analyzer Docker镜像
- **镜像命名**: `hub.trader.com/project/stock-analyzer:TAG`
- **手动触发**: ✅

#### build:monitor
- **触发条件**: 同analyzer
- **执行内容**: 构建Monitor Docker镜像
- **镜像命名**: `hub.trader.com/project/stock-monitor:TAG`
- **手动触发**: ✅

#### build:all
- **触发条件**: 仅Git标签
- **执行内容**: 构建所有服务镜像
- **用途**: 完整版本发布
- **手动触发**: ✅

### 3. Deploy Stage（部署阶段）

#### deploy:dev
- **触发条件**: develop分支
- **部署目标**: 开发环境
- **方式**: Docker Compose
- **URL**: http://dev.stock-monitor.trader.com
- **手动触发**: ✅

#### deploy:prod
- **触发条件**: Git标签
- **部署目标**: 生产环境
- **方式**: Kubernetes (Helm)
- **URL**: http://stock-monitor.trader.com
- **手动触发**: ✅

## 🏷️ 版本标签规则

### 标签格式
```bash
v{major}.{minor}.{patch}

示例：
- v2.0.0   ✅ 正确
- v2.1.3   ✅ 正确
- v10.5.2  ✅ 正确
- 2.0.0    ❌ 错误（缺少v前缀）
- v2.0     ❌ 错误（缺少patch版本）
```

### 镜像标签策略

| Git事件 | 镜像标签 | 示例 |
|---------|----------|------|
| Tag推送 | `{tag}` + `latest` | `v2.0.0`, `latest` |
| Main分支 | `main-{short_sha}` | `main-abc1234` |
| Develop分支 | `develop-{short_sha}` | `develop-def5678` |

## 🚀 使用示例

### 场景1: 开发新功能

```bash
# 1. 创建功能分支
git checkout -b feature/new-feature

# 2. 开发并提交
git add .
git commit -m "feat: 添加新功能"

# 3. 推送到GitLab
git push origin feature/new-feature

# 4. 创建Merge Request到develop分支
# 5. 合并后，develop分支自动运行测试
# 6. 在GitLab UI手动触发部署到dev环境
```

### 场景2: 发布新版本

```bash
# 1. 确保在main分支
git checkout main
git pull origin main

# 2. 创建版本标签
git tag v2.1.0
git push origin v2.1.0

# 3. GitLab自动触发：
#    - 测试（自动）
#    - 构建镜像（手动触发）
#    - 部署生产（手动触发）

# 4. 在GitLab UI查看Pipeline
# 5. 手动点击构建按钮
# 6. 验证镜像后，手动点击部署按钮
```

### 场景3: 只构建特定服务

```bash
# 构建analyzer服务
git tag v2.1.0-analyzer
git push origin v2.1.0-analyzer

# 在GitLab UI手动触发 build:analyzer
```

## 🔧 环境变量配置

在GitLab项目设置中配置以下变量：

### CI/CD Variables

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DOCKER_REGISTRY` | Docker镜像仓库 | hub.trader.com |
| `KUBECONFIG` | Kubernetes配置 | （文件内容） |
| `PROD_SERVER_HOST` | 生产服务器地址 | prod.trader.com |
| `PROD_SERVER_USER` | 生产服务器用户 | deployer |
| `SLACK_WEBHOOK` | Slack通知地址 | https://hooks.slack.com/... |

配置路径: **Settings → CI/CD → Variables**

## 📊 Pipeline 监控

### 查看Pipeline状态
```
GitLab项目页面 → CI/CD → Pipelines
```

### 查看构建日志
```
Pipeline详情 → 点击具体Job → 查看日志输出
```

### Pipeline Badge
在README中添加Pipeline状态徽章：

```markdown
[![pipeline status](https://git.trader.com/trader/live/live_monitor/badges/main/pipeline.svg)](https://git.trader.com/trader/live/live_monitor/-/commits/main)
```

## 🐛 常见问题

### 1. 构建失败：Docker权限错误

**问题**: `permission denied while trying to connect to Docker daemon`

**解决**:
```bash
# 在GitLab Runner机器上执行
sudo usermod -aG docker gitlab-runner
sudo systemctl restart gitlab-runner
```

### 2. 推送镜像失败

**问题**: `unauthorized: authentication required`

**解决**:
```bash
# 在GitLab Runner上登录Docker Registry
docker login hub.trader.com
```

### 3. Helm部署失败

**问题**: `connection refused` 或 `cluster unreachable`

**解决**:
- 检查KUBECONFIG配置是否正确
- 验证GitLab Runner到K8s集群的网络连通性
- 检查Helm charts路径是否存在

### 4. 测试阶段缓存问题

**问题**: 依赖安装缓慢

**解决**: Pipeline已配置cache，首次运行后会加速：
```yaml
cache:
  paths:
    - services/analyzer/.pytest_cache/
    - services/monitor/node_modules/
```

## 🔐 安全最佳实践

1. **敏感信息**: 所有密码、密钥使用GitLab CI/CD变量，不要写在代码中
2. **镜像扫描**: 建议集成Trivy等镜像安全扫描工具
3. **权限控制**: 生产部署设置为Protected branches和Manual trigger
4. **审计日志**: 定期检查Pipeline执行记录

## 📚 扩展阅读

- [GitLab CI/CD官方文档](https://docs.gitlab.com/ee/ci/)
- [Docker最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [Helm部署指南](https://helm.sh/docs/)

## 🆘 获取帮助

如有问题，请联系：
- DevOps团队
- 项目维护者: panwen

---

**提示**: 生产部署前务必在开发环境充分测试！

