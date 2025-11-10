const fs = require('fs');
const path = require('path');
const chokidar = require('chokidar');
const config = require('../config');

/**
 * 文件监控服务
 */
class FileWatcher {
  constructor() {
    this.watchers = new Map();
    this.callbacks = new Map();
  }

  /**
   * 设置文件夹监控
   * @param {string} folder - 监控的文件夹路径
   * @param {string} type - 数据类型 ('stock' | 'index')
   * @param {Function} onChange - 文件变化回调
   * @returns {Object|null} Chokidar监控实例
   */
  watch(folder, type, onChange) {
    if (!fs.existsSync(folder)) {
      console.warn(`⚠️ ${type === 'index' ? '股指' : '股票'}数据文件夹不存在: ${folder}`);
      console.warn(`   请确保 analyzer 服务正在运行`);
      return null;
    }

    const watcher = chokidar.watch(folder, {
      ignored: /(^|[\/\\])\../,
      persistent: true,
      ignoreInitial: false,
      awaitWriteFinish: {
        stabilityThreshold: config.watcher.stabilityThreshold,
        pollInterval: config.watcher.pollInterval
      }
    });

    watcher
      .on('add', filePath => this._handleChange(filePath, type, onChange))
      .on('change', filePath => this._handleChange(filePath, type, onChange))
      .on('unlink', filePath => this._handleUnlink(filePath, type, onChange))
      .on('error', error => console.error('文件监控错误:', error));

    this.watchers.set(type, watcher);
    this.callbacks.set(type, onChange);

    console.log(`✅ ${type === 'index' ? '股指' : '股票'}数据监控已启动: ${folder}`);
    return watcher;
  }

    /**
   * 处理文件变化
   * @private
   */
    _handleChange(filePath, type, onChange) {
      const ext = path.extname(filePath);
      
      // 优先处理 JSON，也支持 CSV
      if (ext === '.json' || ext === '.csv') {
        console.log(`📄 检测到${type === 'index' ? '股指' : '股票'}文件变化: ${path.basename(filePath)}`);
        onChange(filePath);
      }
    }
  
    /**
     * 处理文件删除
     * @private
     */
    _handleUnlink(filePath, type, onChange) {
      console.log(`🗑️ 文件已删除: ${path.basename(filePath)}`);
      onChange(null); // 传递null表示清空数据
    }
  
    /**
     * 加载初始文件（优先 JSON）
     * @param {string} folder - 文件夹路径
     * @param {string} type - 数据类型
     */
    loadInitialFiles(folder, type) {
      if (!fs.existsSync(folder)) {
        console.warn(`⚠️ ${type === 'index' ? '股指' : '股票'}数据文件夹不存在: ${folder}`);
        return;
      }
  
      try {
        const files = fs.readdirSync(folder);
        
        // 优先查找 JSON 文件，回退到 CSV
        const jsonFiles = files.filter(file => file.endsWith('.json'));
        const csvFiles = files.filter(file => file.endsWith('.csv'));
        
        // 优先使用 JSON 文件
        const targetFiles = jsonFiles.length > 0 ? jsonFiles : csvFiles;
        const fileType = jsonFiles.length > 0 ? 'JSON' : 'CSV';
  
        if (targetFiles.length > 0) {
          console.log(`📁 找到 ${targetFiles.length} 个${type === 'index' ? '股指' : '股票'}${fileType}数据文件`);
          
          const callback = this.callbacks.get(type);
          if (callback) {
            // 只加载最新的文件（按修改时间排序）
            const sortedFiles = targetFiles
              .map(file => ({
                name: file,
                path: path.join(folder, file),
                mtime: fs.statSync(path.join(folder, file)).mtime
              }))
              .sort((a, b) => b.mtime - a.mtime);
            
            // 只加载最新的文件
            if (sortedFiles.length > 0) {
              const latest = sortedFiles[0];
              console.log(`📌 加载最新文件: ${latest.name}`);
              callback(latest.path);
            }
          }
        } else {
          console.log(`📂 ${type === 'index' ? '股指' : '股票'}文件夹为空，等待数据生成...`);
        }
      } catch (error) {
        console.error(`读取${type === 'index' ? '股指' : '股票'}文件夹失败:`, error);
      }
    }
  /**
   * 停止所有监控
   */
  async stopAll() {
    const promises = [];
    for (const [type, watcher] of this.watchers.entries()) {
      console.log(`🛑 停止${type === 'index' ? '股指' : '股票'}数据监控`);
      promises.push(watcher.close());
    }
    await Promise.all(promises);
    this.watchers.clear();
    this.callbacks.clear();
  }
}

module.exports = new FileWatcher();

