const redis = require('redis');
const config = require('../config');

/**
 * Redis缓存服务
 */
class CacheService {
  constructor() {
    this.client = null;
    this.enabled = config.redis.enabled;
  }

  /**
   * 连接Redis
   */
  async connect() {
    if (!this.enabled) {
      console.log('⚠️ Redis未启用，将使用内存缓存');
      return;
    }

    try {
      const redisConfig = {
        socket: {
          host: config.redis.host,
          port: config.redis.port
        },
        database: config.redis.db
      };

      if (config.redis.password) {
        redisConfig.password = config.redis.password;
      }

      this.client = redis.createClient(redisConfig);

      this.client.on('error', (err) => 
        console.error('Redis错误:', err.message));
      this.client.on('connect', () => 
        console.log('✅ Redis连接成功'));

      await this.client.connect();
    } catch (error) {
      console.warn('⚠️ Redis连接失败，使用内存缓存:', error.message);
      this.client = null;
      this.enabled = false;
    }
  }

  /**
   * 获取缓存数据
   * @param {string} key - 缓存键
   * @returns {Promise<any>} 缓存数据
   */
  async get(key) {
    if (!this.client) return null;
    try {
      const data = await this.client.get(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.warn('Redis读取失败:', error.message);
      return null;
    }
  }

  /**
   * 设置缓存数据
   * @param {string} key - 缓存键
   * @param {any} value - 缓存值
   * @param {number} ttl - 过期时间（秒）
   * @returns {Promise<boolean>} 是否成功
   */
  async set(key, value, ttl = config.redis.ttl) {
    if (!this.client) return false;
    try {
      await this.client.setEx(key, ttl, JSON.stringify(value));
      return true;
    } catch (error) {
      console.warn('Redis写入失败:', error.message);
      return false;
    }
  }

  /**
   * 删除缓存
   * @param {string} key - 缓存键
   * @returns {Promise<boolean>} 是否成功
   */
  async del(key) {
    if (!this.client) return false;
    try {
      await this.client.del(key);
      return true;
    } catch (error) {
      console.warn('Redis删除失败:', error.message);
      return false;
    }
  }

  /**
   * 关闭连接
   */
  async quit() {
    if (this.client) {
      await this.client.quit();
      console.log('✅ Redis连接已关闭');
    }
  }

  /**
   * 检查是否已连接
   * @returns {boolean}
   */
  isConnected() {
    return this.enabled && this.client !== null;
  }
}

module.exports = new CacheService();

