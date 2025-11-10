require('dotenv').config();

module.exports = {
  // 服务器配置
  server: {
    port: parseInt(process.env.PORT) || 8006,
    env: process.env.NODE_ENV || 'development',
    timezone: process.env.TZ || 'Asia/Shanghai'
  },

  // 数据文件夹配置
  folders: {
    stock: process.env.STOCK_FOLDER || '/app/data/test_result',
    index: process.env.INDEX_FOLDER || '/app/data/index_data'
  },

  // Redis配置
  redis: {
    enabled: process.env.USE_REDIS === 'true',
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT) || 6379,
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_DB) || 0,
    ttl: parseInt(process.env.REDIS_TTL) || 60
  },

  // 文件监控配置
  watcher: {
    stabilityThreshold: 2000,
    pollInterval: 100
  },

  // API配置
  api: {
    defaultPageSize: 100,
    maxPageSize: 1000
  }
};

