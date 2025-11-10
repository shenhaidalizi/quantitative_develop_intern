/**
 * 过滤数据
 * @param {Array} data - 要过滤的数据
 * @param {string} search - 搜索关键词
 * @returns {Array} 过滤后的数据
 */
function filterData(data, search) {
  if (!search) return data;
  
  const searchLower = search.toLowerCase();
  return data.filter(item =>
    item.code.toLowerCase().includes(searchLower) ||
    item.Name.toLowerCase().includes(searchLower)
  );
}

module.exports = {
  filterData
};

