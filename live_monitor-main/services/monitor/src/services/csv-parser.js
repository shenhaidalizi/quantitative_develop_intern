const fs = require('fs');
const path = require('path');
/**
 * 解析股票数据文件（自动识别 JSON 或 CSV）
 * @param {string} filePath - 文件路径（CSV 或 JSON）
 * @returns {Array} 解析后的股票数据
 */
function parseStockCSV(filePath) {
  // 如果传入的就是 JSON 文件，直接解析
  if (filePath.endsWith('.json')) {
    try {
      const startTime = Date.now();
      const content = fs.readFileSync(filePath, 'utf-8');
      const data = JSON.parse(content);
      const parseTime = Date.now() - startTime;
      
      console.log(`✅ JSON解析: ${path.basename(filePath)}, ${data.length} 条记录, 耗时: ${parseTime}ms`);
      return data;
    } catch (error) {
      console.error(`❌ JSON解析失败: ${error.message}`);
      return [];
    }
  }
  
  // 如果是 CSV 文件，尝试查找对应的 JSON 文件
  if (filePath.endsWith('.csv')) {
    const jsonPath = filePath.replace(/\.csv$/, '.json');
    
    if (fs.existsSync(jsonPath)) {
      try {
        const startTime = Date.now();
        const content = fs.readFileSync(jsonPath, 'utf-8');
        const data = JSON.parse(content);
        const parseTime = Date.now() - startTime;
        
        console.log(`✅ JSON解析(优先): ${path.basename(jsonPath)}, ${data.length} 条记录, 耗时: ${parseTime}ms`);
        return data;
      } catch (error) {
        console.warn(`⚠️ JSON解析失败，回退到CSV: ${error.message}`);
      }
    }
    
    // 回退到 CSV 解析
    return parseStockCSVLegacy(filePath);
  }
  
  // 未知文件类型
  console.error(`❌ 不支持的文件类型: ${filePath}`);
  return [];
}

/**
 * 传统 CSV 解析（备用）
 * @param {string} filePath - CSV文件路径
 * @returns {Array} 解析后的股票数据
 */
function parseStockCSVLegacy(filePath) {
  try {
    const startTime = Date.now();
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    
    if (lines.length <= 1) {
      console.warn('CSV文件内容不足:', filePath);
      return [];
    }

    const data = lines.slice(1).map(line => {
      const values = line.split(',');
      if (values.length < 12) return null;
      
      const [
        code, Name, Price, Chg, Vol,
        rolling1_z_score, rolling5_z_score,
        rolling10_z_score, rolling30_z_score,
        rolling_full_z_score, Chg5, Chg30
      ] = values;
      
      if (!code || !code.trim()) return null;
      
      return {
        code: code.trim(),
        Name: Name?.trim() || '',
        Price: parseFloat(Price) || 0,
        Chg: parseFloat(Chg) || 0,
        Vol: parseFloat(Vol) || 0,
        r1_z: parseFloat(rolling1_z_score) || 0,
        r5_z: parseFloat(rolling5_z_score) || 0,
        r10_z: parseFloat(rolling10_z_score) || 0,
        r30_z: parseFloat(rolling30_z_score) || 0,
        rolling_full: parseFloat(rolling_full_z_score) || 0,
        Chg5: parseFloat(Chg5) || 0,
        Chg30: parseFloat(Chg30) || 0
      };
    }).filter(Boolean);

    const parseTime = Date.now() - startTime;
    console.log(`✅ CSV解析: ${path.basename(filePath)}, ${data.length} 条记录, 耗时: ${parseTime}ms`);
    return data;
  } catch (error) {
    console.error('❌ 解析CSV失败:', error);
    return [];
  }
}

/**
 * 解析股指数据文件（自动识别 JSON 或 CSV）
 * @param {string} filePath - 文件路径
 * @returns {Array} 解析后的股指数据
 */
function parseIndexCSV(filePath) {
  // 如果传入的是 JSON 文件，直接解析
  if (filePath.endsWith('.json')) {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const data = JSON.parse(content);
      console.log(`✅ JSON解析: ${path.basename(filePath)}, ${data.length} 条记录`);
      return data;
    } catch (error) {
      console.error(`❌ JSON解析失败: ${error.message}`);
      return [];
    }
  }
  
  // 如果是 CSV，尝试找 JSON
  if (filePath.endsWith('.csv')) {
    const jsonPath = filePath.replace(/\.csv$/, '.json');
    
    if (fs.existsSync(jsonPath)) {
      try {
        const content = fs.readFileSync(jsonPath, 'utf-8');
        const data = JSON.parse(content);
        console.log(`✅ JSON解析(优先): ${path.basename(jsonPath)}, ${data.length} 条记录`);
        return data;
      } catch (error) {
        console.warn(`⚠️ JSON解析失败，回退到CSV: ${error.message}`);
      }
    }
    
    // 回退到 CSV
    return parseIndexCSVLegacy(filePath);
  }
  
  console.error(`❌ 不支持的文件类型: ${filePath}`);
  return [];
}

/**
 * 传统股指 CSV 解析（备用）
 */
function parseIndexCSVLegacy(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    
    if (lines.length <= 1) {
      console.warn('CSV文件内容不足:', filePath);
      return [];
    }

    const data = lines.slice(1).map(line => {
      const values = line.split(',');
      if (values.length < 11) return null;
      
      const [
        code, Name, Chg, Vol,
        rolling1_z_score, rolling5_z_score,
        rolling10_z_score, rolling30_z_score,
        rolling_full_z_score, Chg5, Chg30
      ] = values;
      
      if (!code || !code.trim()) return null;
      
      return {
        code: code.trim(),
        Name: Name?.trim() || '',
        Chg: parseFloat(Chg) || 0,
        Vol: parseFloat(Vol) || 0,
        r1_z: parseFloat(rolling1_z_score) || 0,
        r5_z: parseFloat(rolling5_z_score) || 0,
        r10_z: parseFloat(rolling10_z_score) || 0,
        r30_z: parseFloat(rolling30_z_score) || 0,
        rolling_full: parseFloat(rolling_full_z_score) || 0,
        Chg5: parseFloat(Chg5) || 0,
        Chg30: parseFloat(Chg30) || 0
      };
    }).filter(Boolean);

    console.log(`✅ CSV解析: ${path.basename(filePath)}, ${data.length} 条记录`);
    return data;
  } catch (error) {
    console.error('❌ 解析股指CSV失败:', error);
    return [];
  }
}

module.exports = {
  parseStockCSV,
  parseIndexCSV
};