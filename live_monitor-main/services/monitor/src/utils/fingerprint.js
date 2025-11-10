/**
 * 生成数据指纹（用于快速检查数据是否变化）
 * @param {Array} data - 数据数组
 * @param {string} lastUpdated - 最后更新时间
 * @returns {string} 数据指纹
 */
function generateFingerprint(data, lastUpdated) {
  if (!data || data.length === 0) return 'empty';
  
  // 取前3条数据生成样本
  const sample = data.slice(0, 3).map(item => 
    `${item.code}_${item.Chg}_${item.r5_z || 0}`
  ).join('|');
  
  return `${data.length}_${sample}_${lastUpdated}`;
}

module.exports = {
  generateFingerprint
};

