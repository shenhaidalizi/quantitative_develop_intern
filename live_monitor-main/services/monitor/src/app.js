const express = require('express');
const cors = require('cors');
const compression = require('compression');
const path = require('path');
const routes = require('./routes');
const { errorHandler, logger } = require('./middlewares');

/**
 * 创建Express应用
 */
function createApp() {
  const app = express();

  // 基础中间件
  app.use(cors());
  app.use(express.json());
  app.use(compression()); // 启用gzip压缩
  app.use(logger); // 请求日志

  // 静态文件服务
  app.use(express.static(path.join(__dirname, 'public')));

  // API路由
  app.use('/api', routes);

  // 错误处理中间件（必须放在最后）
  app.use(errorHandler);

  return app;
}

module.exports = createApp;

