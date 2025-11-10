const createApp = require('./app');
const config = require('./config');
const cacheService = require('./services/cache');
const dataManager = require('./services/data-manager');

/**
 * 启动服务器
 */
async function startServer() {
  try {
    console.log('🚀 正在启动股票监控服务...');
    console.log('─'.repeat(50));

    // 初始化Redis缓存
    await cacheService.connect();

    // 初始化数据管理器
    await dataManager.initialize();

    // 创建Express应用
    const app = createApp();

    // 启动HTTP服务器
    const server = app.listen(config.server.port, () => {
      console.log('');
      console.log('✅ 股票监控服务启动成功!');
      console.log('─'.repeat(50));
      console.log(`📡 服务地址: http://localhost:${config.server.port}`);
      console.log(`📊 API状态: http://localhost:${config.server.port}/api/status`);
      console.log(`📂 监控股票文件夹: ${config.folders.stock}`);
      console.log(`📂 监控股指文件夹: ${config.folders.index}`);
      console.log(`💾 Redis缓存: ${cacheService.isConnected() ? '✅ 已启用' : '⚠️ 未启用'}`);
      console.log(`🌍 环境: ${config.server.env}`);
      console.log('─'.repeat(50));
    });

    // 优雅关闭
    const shutdown = async (signal) => {
      console.log(`\n\n🛑 收到 ${signal} 信号，正在优雅关闭...`);
      
      // 停止接收新请求
      server.close(() => {
        console.log('✅ HTTP服务器已关闭');
      });

      // 清理资源
      await dataManager.cleanup();
      await cacheService.quit();

      console.log('✅ 所有资源已清理完成');
      process.exit(0);
    };

    process.on('SIGINT', () => shutdown('SIGINT'));
    process.on('SIGTERM', () => shutdown('SIGTERM'));

    // 未捕获的异常处理
    process.on('uncaughtException', (error) => {
      console.error('❌ 未捕获的异常:', error);
      shutdown('uncaughtException');
    });

    process.on('unhandledRejection', (reason, promise) => {
      console.error('❌ 未处理的Promise拒绝:', reason);
      shutdown('unhandledRejection');
    });

  } catch (error) {
    console.error('❌ 服务启动失败:', error);
    process.exit(1);
  }
}

// 启动服务
if (require.main === module) {
  startServer();
}

module.exports = { startServer };

