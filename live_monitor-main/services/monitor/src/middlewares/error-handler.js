/**
 * 统一错误处理中间件
 */
function errorHandler(err, req, res, next) {
  console.error('❌ 错误:', err);

  const status = err.status || 500;
  const message = err.message || '服务器内部错误';

  res.status(status).json({
    error: message,
    status,
    timestamp: new Date().toISOString()
  });
}

module.exports = errorHandler;

