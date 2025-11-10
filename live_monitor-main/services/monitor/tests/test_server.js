/**
 * 测试服务器启动脚本
 * 自动设置测试环境并启动服务
 */

const { setupTestEnvironment, startContinuousGeneration } = require('./test_data_generator');
const path = require('path');
const fs = require('fs');

console.log('🧪 测试模式启动');
console.log('='.repeat(60));

// 设置测试环境
const { stockDir, indexDir } = setupTestEnvironment();

// 创建临时.env文件
const envPath = path.join(__dirname, '.env.test');
const envContent = `
PORT=3000
STOCK_FOLDER=${stockDir}
INDEX_FOLDER=${indexDir}
USE_REDIS=false
`;

fs.writeFileSync(envPath, envContent.trim(), 'utf-8');
console.log(`\n📝 临时配置已创建: ${envPath}\n`);

// 设置环境变量
process.env.PORT = '3000';
process.env.STOCK_FOLDER = stockDir;
process.env.INDEX_FOLDER = indexDir;
process.env.USE_REDIS = 'false';

// 启动持续数据生成（每30秒）
startContinuousGeneration(stockDir, indexDir, 30);

// 启动服务器
console.log('\n🚀 启动测试服务器...\n');
require('./server.js');

// 清理
process.on('SIGINT', () => {
  console.log('\n\n🧹 清理测试环境...');
  if (fs.existsSync(envPath)) {
    fs.unlinkSync(envPath);
  }
  console.log('✅ 清理完成');
  process.exit(0);
});