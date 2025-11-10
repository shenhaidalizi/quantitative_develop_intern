const express = require('express');
const router = express.Router();

const statusRouter = require('./status');
const stockRouter = require('./stock');
const indexDataRouter = require('./index-data');

// 注册路由
router.use('/status', statusRouter);
router.use('/stock-data', stockRouter);
router.use('/index-data', indexDataRouter);

// 兼容旧API路径
router.get('/data-fingerprint', statusRouter);
router.post('/reload', statusRouter);

module.exports = router;

