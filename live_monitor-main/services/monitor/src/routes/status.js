const express = require('express');
const router = express.Router();
const config = require('../config');
const cacheService = require('../services/cache');
const dataManager = require('../services/data-manager');
const { generateFingerprint } = require('../utils');

/**
 * GET /api/status
 * 系统状态检查
 */
router.get('/', (req, res) => {
  const stats = dataManager.getStats();
  
  res.json({
    status: 'running',
    lastUpdated: stats.lastUpdated,
    monitoredFolders: {
      stock: config.folders.stock,
      index: config.folders.index
    },
    stockCount: stats.stockCount,
    indexCount: stats.indexCount,
    redis: cacheService.isConnected(),
    timestamp: new Date().toISOString()
  });
});

/**
 * GET /api/data-fingerprint
 * 数据指纹（轻量级检查数据是否变化）
 */
router.get('/fingerprint', async (req, res) => {
  const stockData = await dataManager.getStockData();
  const indexData = await dataManager.getIndexData();
  const lastUpdated = dataManager.getLastUpdated();

  res.json({
    stockFingerprint: generateFingerprint(stockData, lastUpdated),
    indexFingerprint: generateFingerprint(indexData, lastUpdated),
    lastUpdated,
    stockCount: stockData.length,
    indexCount: indexData.length
  });
});

/**
 * POST /api/reload
 * 手动触发数据重新加载
 */
router.post('/reload', async (req, res) => {
  try {
    await dataManager.reload();
    res.json({
      message: '数据已重新加载',
      lastUpdated: dataManager.getLastUpdated()
    });
  } catch (error) {
    res.status(500).json({
      error: '重新加载失败',
      message: error.message
    });
  }
});

module.exports = router;

