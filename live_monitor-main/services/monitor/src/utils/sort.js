/**
 * 对数据进行排序
 * @param {Array} data - 要排序的数据
 * @param {string} sortBy - 排序字段
 * @param {string} order - 排序顺序 ('asc' | 'desc')
 * @returns {Array} 排序后的数据
 */
function sortData(data, sortBy = 'r5_z', order = 'desc') {
  return [...data].sort((a, b) => {
    const valueA = a[sortBy] || 0;
    const valueB = b[sortBy] || 0;
    return order === 'desc' ? valueB - valueA : valueA - valueB;
  });
}

module.exports = {
  sortData
};

