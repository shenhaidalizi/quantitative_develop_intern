const express = require('express');
const router = express.Router();
const dataManager = require('../services/data-manager');
const { sortData, filterData, paginate } = require('../utils');

/**
 * GET /api/index-data
 * 获取股指数据（支持分页、排序、筛选）
 */
router.get('/', async (req, res, next) => {
  try {
    // 获取原始数据
    let data = await dataManager.getIndexData();

    // 筛选
    if (req.query.search) {
      data = filterData(data, req.query.search);
    }

    // 排序
    const sortBy = req.query.sort || 'r5_z';
    const order = req.query.order || 'desc';
    data = sortData(data, sortBy, order);

    // 分页
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || null; // null表示返回全部
    const result = paginate(data, page, limit);

    res.json({
      lastUpdated: dataManager.getLastUpdated(),
      data: result.data,
      count: result.data.length,
      total: result.total,
      page: result.page,
      totalPages: result.totalPages
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;

