FROM hub.zoyutech.com/library/node:24

WORKDIR /app

# 设置环境变量
ENV NODE_ENV=production
ENV TZ=Asia/Shanghai

# 复制package文件
COPY package*.json ./

# 安装依赖（仅生产依赖）
RUN npm install --omit=dev && \
    npm cache clean --force

# 复制源代码
COPY src/ ./src/

# 非root用户运行
RUN groupadd -g 1001 nodejs && \
    useradd -r -u 1001 -g nodejs nodejs && \
    chown -R nodejs:nodejs /app

USER nodejs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8006/api/status || exit 1

# 暴露端口
EXPOSE 8006

# 启动服务
CMD ["node", "src/server.js"]
