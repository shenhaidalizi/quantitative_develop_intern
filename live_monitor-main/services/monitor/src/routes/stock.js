const express = require('express');
const router = express.Router();
const dataManager = require('../services/data-manager');
const { sortData, filterData, paginate } = require('../utils');

/**
 * GET /api/stock-data
 * 获取股票数据（支持分页、排序、筛选、自选股）
 * 查询参数:
 *  - sort: 排序字段 (默认: rolling_full)
 *  - order: 排序方向 (默认: desc)
 *  - limit: 返回数量限制 (默认: 500)
 *  - watchlist: 自选股代码列表，逗号分隔 (例如: "600000,000001")
 */
router.get('/', async (req, res, next) => {
  try {
    const startTime = Date.now();
    
    // 获取原始数据
    let data = await dataManager.getStockData();

    // 筛选
    if (req.query.search) {
      data = filterData(data, req.query.search);
    }

    // 排序 - 默认按 rolling_full (allz) 降序
    const sortBy = req.query.sort || 'rolling_full';
    const order = req.query.order || 'desc';
    data = sortData(data, sortBy, order);

    // 处理自选股逻辑（优化：使用 Set 快速查找）
    const limit = parseInt(req.query.limit) || 500;
    let finalData;
    
    if (req.query.watchlist) {
      const watchlistCodes = req.query.watchlist.split(',').map(c => c.trim()).filter(Boolean);
      
      if (watchlistCodes.length > 0) {
        const watchlistSet = new Set(watchlistCodes);
        const watchlistData = [];
        const topData = [];
        let topCount = 0;
        
        // 单次遍历，同时收集自选股和top数据
        for (const item of data) {
          if (watchlistSet.has(item.code)) {
            watchlistData.push(item);
          } else if (topCount < limit) {
            topData.push(item);
            topCount++;
          }
          
          // 如果已经收集够了，可以提前退出
          if (watchlistData.length === watchlistCodes.length && topCount >= limit) {
            break;
          }
        }
        
        finalData = [...watchlistData, ...topData];
      } else {
        finalData = data.slice(0, limit);
      }
    } else {
      finalData = data.slice(0, limit);
    }

    const processingTime = Date.now() - startTime;
    
    res.json({
      lastUpdated: dataManager.getLastUpdated(),
      data: finalData,
      count: finalData.length,
      total: data.length,
      processingTime: processingTime
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;

