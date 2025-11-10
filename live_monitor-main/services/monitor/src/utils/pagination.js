/**
 * 对数据进行分页
 * @param {Array} data - 要分页的数据
 * @param {number} page - 页码（从1开始）
 * @param {number} limit - 每页数量
 * @returns {Object} 分页结果
 */
function paginate(data, page = 1, limit = null) {
  const total = data.length;
  
  // 如果没有指定limit，返回全部数据
  if (!limit || limit <= 0) {
    return {
      data,
      total,
      page: 1,
      totalPages: 1
    };
  }

  const start = (page - 1) * limit;
  const end = start + limit;
  const paginatedData = data.slice(start, end);
  const totalPages = Math.ceil(total / limit);

  return {
    data: paginatedData,
    total,
    page,
    totalPages
  };
}

module.exports = {
  paginate
};

