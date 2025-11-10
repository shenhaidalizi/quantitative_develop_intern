const config = require('../config');
const cacheService = require('./cache');
const fileWatcher = require('./file-watcher');
const { parseStockCSV, parseIndexCSV } = require('./csv-parser');

/**
 * 数据管理服务
 */
class DataManager {
  constructor() {
    this.stockData = [];
    this.indexData = [];
    this.lastUpdated = new Date().toISOString();
  }

  /**
   * 初始化数据管理器
   */
  async initialize() {
    // 设置股票数据监控
    fileWatcher.watch(
      config.folders.stock,
      'stock',
      (filePath) => this._handleStockChange(filePath)
    );

    // 设置股指数据监控
    fileWatcher.watch(
      config.folders.index,
      'index',
      (filePath) => this._handleIndexChange(filePath)
    );

    // 加载初始数据
    fileWatcher.loadInitialFiles(config.folders.stock, 'stock');
    fileWatcher.loadInitialFiles(config.folders.index, 'index');

    console.log('✅ 数据管理器初始化完成');
  }

  /**
   * 处理股票数据变化
   * @private
   */
  async _handleStockChange(filePath) {
    if (!filePath) {
      this.stockData = [];
      await cacheService.del('stockData');
      return;
    }

    const data = parseStockCSV(filePath);
    this.stockData = data;
    this.lastUpdated = new Date().toISOString();

    // 更新缓存
    await cacheService.set('stockData', {
      data,
      lastUpdated: this.lastUpdated,
      count: data.length
    });

    console.log(`✅ 股票数据已更新: ${data.length} 条记录`);
  }

  /**
   * 处理股指数据变化
   * @private
   */
  async _handleIndexChange(filePath) {
    if (!filePath) {
      this.indexData = [];
      await cacheService.del('indexData');
      return;
    }

    const data = parseIndexCSV(filePath);
    this.indexData = data;
    this.lastUpdated = new Date().toISOString();

    // 更新缓存
    await cacheService.set('indexData', {
      data,
      lastUpdated: this.lastUpdated,
      count: data.length
    });

    console.log(`✅ 股指数据已更新: ${data.length} 条记录`);
  }

  /**
   * 获取股票数据
   * @returns {Promise<Array>}
   */
  async getStockData() {
    // 优先从缓存获取
    const cached = await cacheService.get('stockData');
    if (cached && cached.data) {
      return cached.data;
    }
    return this.stockData;
  }

  /**
   * 获取股指数据
   * @returns {Promise<Array>}
   */
  async getIndexData() {
    // 优先从缓存获取
    const cached = await cacheService.get('indexData');
    if (cached && cached.data) {
      return cached.data;
    }
    return this.indexData;
  }

  /**
   * 获取最后更新时间
   * @returns {string}
   */
  getLastUpdated() {
    return this.lastUpdated;
  }

  /**
   * 获取数据统计
   * @returns {Object}
   */
  getStats() {
    return {
      stockCount: this.stockData.length,
      indexCount: this.indexData.length,
      lastUpdated: this.lastUpdated
    };
  }

  /**
   * 手动重新加载数据
   */
  async reload() {
    fileWatcher.loadInitialFiles(config.folders.stock, 'stock');
    fileWatcher.loadInitialFiles(config.folders.index, 'index');
    console.log('🔄 数据已重新加载');
  }

  /**
   * 清理资源
   */
  async cleanup() {
    await fileWatcher.stopAll();
    console.log('✅ 数据管理器已清理');
  }
}

module.exports = new DataManager();

