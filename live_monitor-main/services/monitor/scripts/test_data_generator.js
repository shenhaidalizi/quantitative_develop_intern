const fs = require('fs');
const path = require('path');

/**
 * 测试数据生成器
 * 用于在没有实时数据时生成模拟数据进行测试
 */

// 生成随机数
function randomFloat(min, max, decimals = 2) {
  const value = Math.random() * (max - min) + min;
  return parseFloat(value.toFixed(decimals));
}

// 生成随机股票代码
function generateStockCode(index, isIndex = false) {
  if (isIndex) {
    const indexCodes = ['000001', '399001', '399006', '000016', '000300'];
    return indexCodes[index % indexCodes.length];
  }
  const prefix = ['60', '00', '30'][Math.floor(Math.random() * 3)];
  const suffix = String(index).padStart(4, '0');
  return prefix + suffix;
}

// 生成股票名称
function generateStockName(code, isIndex = false) {
  if (isIndex) {
    const names = {
      '000001': '上证指数',
      '399001': '深证成指',
      '399006': '创业板指',
      '000016': '上证50',
      '000300': '沪深300'
    };
    return names[code] || '指数';
  }
  return `测试股票${code}`;
}

// 生成单条股票数据
function generateStockItem(index) {
  const code = generateStockCode(index);
  return {
    code,
    Name: generateStockName(code),
    Price: randomFloat(5, 200),
    Chg: randomFloat(-10, 10),
    Vol: randomFloat(1000, 1000000),
    r1_z: randomFloat(-3, 3),
    r5_z: randomFloat(-3, 3),
    r10_z: randomFloat(-3, 3),
    r30_z: randomFloat(-3, 3),
    rolling_full: randomFloat(-3, 3),
    Chg5: randomFloat(-5, 5),
    Chg30: randomFloat(-15, 15)
  };
}

// 生成单条股指数据
function generateIndexItem(index) {
  const code = generateStockCode(index, true);
  return {
    code,
    Name: generateStockName(code, true),
    Chg: randomFloat(-5, 5),
    Vol: randomFloat(100000, 10000000),
    r1_z: randomFloat(-3, 3),
    r5_z: randomFloat(-3, 3),
    r10_z: randomFloat(-3, 3),
    r30_z: randomFloat(-3, 3),
    rolling_full: randomFloat(-3, 3),
    Chg5: randomFloat(-3, 3),
    Chg30: randomFloat(-10, 10)
  };
}

// 生成CSV文件
function generateCSV(count, isIndex = false, outputPath) {
  const headers = isIndex 
    ? ['code', 'Name', 'Chg', 'Vol', 'rolling1_z_score', 'rolling5_z_score', 
       'rolling10_z_score', 'rolling30_z_score', 'rolling_full_z_score', 'Chg5', 'Chg30']
    : ['code', 'Name', 'Price', 'Chg', 'Vol', 'rolling1_z_score', 'rolling5_z_score', 
       'rolling10_z_score', 'rolling30_z_score', 'rolling_full_z_score', 'Chg5', 'Chg30'];
  
  const rows = [headers.join(',')];
  
  for (let i = 0; i < count; i++) {
    const item = isIndex ? generateIndexItem(i) : generateStockItem(i);
    const row = isIndex
      ? [item.code, item.Name, item.Chg, item.Vol, item.r1_z, item.r5_z, 
         item.r10_z, item.r30_z, item.rolling_full, item.Chg5, item.Chg30]
      : [item.code, item.Name, item.Price, item.Chg, item.Vol, item.r1_z, item.r5_z, 
         item.r10_z, item.r30_z, item.rolling_full, item.Chg5, item.Chg30];
    rows.push(row.join(','));
  }
  
  fs.writeFileSync(outputPath, rows.join('\n'), 'utf-8');
  console.log(`✅ 生成${isIndex ? '股指' : '股票'}测试数据: ${outputPath} (${count}条)`);
}

// 创建测试环境
function setupTestEnvironment() {
  const testDir = path.join(__dirname, 'test_data');
  const stockDir = path.join(testDir, 'test_result');
  const indexDir = path.join(testDir, 'index_data');
  
  // 创建目录
  [testDir, stockDir, indexDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });
  
  // 生成测试数据
  const timestamp = new Date().toTimeString().split(' ')[0].replace(/:/g, '');
  generateCSV(3000, false, path.join(stockDir, `test_${timestamp}_idx100.csv`));
  generateCSV(5, true, path.join(indexDir, `${new Date().toTimeString().split(' ')[0]}.csv`));
  
  console.log('\n📁 测试环境设置完成:');
  console.log(`   股票数据目录: ${stockDir}`);
  console.log(`   股指数据目录: ${indexDir}`);
  console.log('\n💡 请在 .env 文件中设置:');
  console.log(`   STOCK_FOLDER=${stockDir}`);
  console.log(`   INDEX_FOLDER=${indexDir}`);
  
  return { stockDir, indexDir };
}

// 持续生成测试数据（模拟实时更新）
function startContinuousGeneration(stockDir, indexDir, intervalSeconds = 60) {
  console.log(`\n🔄 开始持续生成测试数据（每${intervalSeconds}秒更新一次）...`);
  console.log('   按 Ctrl+C 停止\n');
  
  setInterval(() => {
    const timestamp = new Date().toTimeString().split(' ')[0].replace(/:/g, '');
    const timeStr = new Date().toTimeString().split(' ')[0];
    
    generateCSV(3000, false, path.join(stockDir, `test_${timestamp}_idx100.csv`));
    generateCSV(5, true, path.join(indexDir, `${timeStr}.csv`));
    
    console.log(`⏰ ${new Date().toLocaleTimeString()} - 数据已更新`);
  }, intervalSeconds * 1000);
}

// 命令行使用
if (require.main === module) {
  const args = process.argv.slice(2);
  const continuous = args.includes('--continuous') || args.includes('-c');
  const interval = parseInt(args.find(arg => arg.startsWith('--interval='))?.split('=')[1]) || 60;
  
  console.log('🧪 测试数据生成器');
  console.log('='.repeat(50));
  
  const { stockDir, indexDir } = setupTestEnvironment();
  
  if (continuous) {
    startContinuousGeneration(stockDir, indexDir, interval);
  } else {
    console.log('\n✅ 完成！使用以下命令启动持续生成:');
    console.log('   node test_data_generator.js --continuous');
    console.log('   node test_data_generator.js --continuous --interval=30');
  }
}

module.exports = {
  generateStockItem,
  generateIndexItem,
  generateCSV,
  setupTestEnvironment,
  startContinuousGeneration
};