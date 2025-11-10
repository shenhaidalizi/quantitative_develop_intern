// 建议修改二：实现 pipeline 逻辑（append + 批量取回回复）
// 文件：/home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client.cpp
#include "redis_client.h"
#include <hiredis/hiredis.h>
#include <sys/time.h>
#include <cstdio>
#include <cstdlib>

RedisClient::RedisClient() : ctx_(nullptr) {}
RedisClient::~RedisClient() { close(); }

bool RedisClient::connect(const std::string& host, int port,
                          const std::string& username,
                          const std::string& password,
                          int db) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (ctx_) return true;
  timeval timeout{2,0};
  ctx_ = redisConnectWithTimeout(host.empty() ? "127.0.0.1" : host.c_str(),
                                 port > 0 ? port : 6379, timeout);
  if (!ctx_ || ctx_->err) { if (ctx_) { redisFree(ctx_); ctx_=nullptr; } return false; }
  if (!username.empty() || !password.empty()) {
    if (!username.empty()) { if (!authAcl_(username, password)) { close(); return false; } }
    else { if (!authLegacy_(password)) { close(); return false; } }
  }
  if (!ping_()) { close(); return false; }
  if (db >= 0 && !select_(db)) { close(); return false; }
  return true;
}

void RedisClient::close() {
  std::lock_guard<std::mutex> lk(mtx_);
  flushPendingLocked_();
  if (ctx_) { redisFree(ctx_); ctx_ = nullptr; }
}

// 新增：pipeline 控制
void RedisClient::setPipeline(bool enabled, int window_cmds) {
  std::lock_guard<std::mutex> lk(mtx_);
  pipeline_   = enabled;
  pipe_window_= enabled ? (window_cmds > 0 ? window_cmds : 0) : 0;
  pending_    = 0;
}
bool RedisClient::flushPipeline() {
  std::lock_guard<std::mutex> lk(mtx_);
  return flushPendingLocked_();
}
bool RedisClient::flushPendingLocked_() {
  if (!ctx_ || pending_ <= 0) return true;
  bool ok = true;
  for (int i = 0; i < pending_; ++i) {
    void* rp = nullptr;
    if (redisGetReply(ctx_, &rp) != REDIS_OK || !rp) { ok = false; continue; }
    redisReply* rr = (redisReply*)rp;
    if (rr->type == REDIS_REPLY_ERROR) ok = false;
    if (rr) freeReplyObject(rr);
  }
  pending_ = 0;
  return ok;
}

// 流写入仍按立即发送
bool RedisClient::writeTickStream(const std::string& stream_key,
                                  const std::string& inst,
                                  double last, double bid1, double ask1,
                                  int64_t ts_ms) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;
  redisReply* r = (redisReply*)redisCommand(ctx_,
      "XADD %s * inst %s last %.10f bid1 %.10f ask1 %.10f ts %lld",
      stream_key.c_str(), inst.c_str(), last, bid1, ask1, (long long)ts_ms);
  bool ok = commandOk_(r); if (r) freeReplyObject(r);
  return ok;
}

// 改写：支持 pipeline
bool RedisClient::writeTickString(const std::string& string_key_prefix,
    const std::string& inst, double last, double bid1, double ask1,
    int64_t ts_ms, int ttl_sec) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;

  char key[256]; std::snprintf(key, sizeof(key), "%s%s", string_key_prefix.c_str(), inst.c_str());
  char val[512];
  std::snprintf(val, sizeof(val),
    "{\"inst\":\"%s\",\"last\":%.10f,\"bid1\":%.10f,\"ask1\":%.10f,\"ts\":%lld}",
    inst.c_str(), last, bid1, ask1, (long long)ts_ms);

  if (!pipeline_) {
    redisReply* r = (redisReply*)redisCommand(ctx_, "SET %s %s", key, val);
    bool ok = commandOk_(r); if (r) freeReplyObject(r);
    if (ok && ttl_sec > 0) ok = expire_(key, ttl_sec);
    return ok;
  }

  // pipeline：append 命令并按阈值批量取回回复
  if (redisAppendCommand(ctx_, "SET %s %s", key, val) == REDIS_OK) ++pending_;
  if (ttl_sec > 0) { if (redisAppendCommand(ctx_, "EXPIRE %s %d", key, ttl_sec) == REDIS_OK) ++pending_; }
  if (pipe_window_ > 0 && pending_ >= pipe_window_) return flushPendingLocked_();
  return true;
}

bool RedisClient::writeTickHash(const std::string& hash_key_prefix,
                                const std::string& inst,
                                double last, double bid1, double ask1,
                                int64_t ts_ms, int ttl_sec) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;

  char key[256]; std::snprintf(key, sizeof(key), "%s%s", hash_key_prefix.c_str(), inst.c_str());

  if (!pipeline_) {
    redisReply* r = (redisReply*)redisCommand(ctx_,
        "HSET %s last %.10f bid1 %.10f ask1 %.10f ts %lld",
        key, last, bid1, ask1, (long long)ts_ms);
    bool ok = commandOk_(r); if (r) freeReplyObject(r);
    if (ok && ttl_sec > 0) ok = expire_(key, ttl_sec);
    return ok;
  }

  if (redisAppendCommand(ctx_, "HSET %s last %.10f bid1 %.10f ask1 %.10f ts %lld",
                         key, last, bid1, ask1, (long long)ts_ms) == REDIS_OK) ++pending_;
  if (ttl_sec > 0) { if (redisAppendCommand(ctx_, "EXPIRE %s %d", key, ttl_sec) == REDIS_OK) ++pending_; }
  if (pipe_window_ > 0 && pending_ >= pipe_window_) return flushPendingLocked_();
  return true;
}

bool RedisClient::authLegacy_(const std::string& password) {
  redisReply* r = (redisReply*)redisCommand(ctx_, "AUTH %s", password.c_str());
  bool ok = commandStatusIs_(r, "OK");
  if (r) freeReplyObject(r);
  return ok;
}

bool RedisClient::authAcl_(const std::string& username, const std::string& password) {
  redisReply* r = (redisReply*)redisCommand(ctx_, "AUTH %s %s", username.c_str(), password.c_str());
  bool ok = commandStatusIs_(r, "OK");
  if (r) freeReplyObject(r);
  return ok;
}

// 将以下实现追加到 /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client.cpp 末尾（保持两空格缩进）

bool RedisClient::ping_() {
  redisReply* r = (redisReply*)redisCommand(ctx_, "PING");
  bool ok = false;
  if (r) {
    if ((r->type == REDIS_REPLY_STATUS && r->str && std::string(r->str) == "PONG") ||
        (r->type == REDIS_REPLY_STRING && r->str && std::string(r->str) == "PONG")) {
      ok = true;
    }
    freeReplyObject(r);
  }
  return ok;
}

bool RedisClient::select_(int db) {
  redisReply* r = (redisReply*)redisCommand(ctx_, "SELECT %d", db);
  bool ok = commandStatusIs_(r, "OK");
  if (r) freeReplyObject(r);
  return ok;
}

bool RedisClient::commandOk_(redisReply* r) {
  if (!r) { std::fprintf(stderr, "[redis] null reply\n"); return false; }
  if (r->type == REDIS_REPLY_ERROR) {
    std::fprintf(stderr, "[redis] error: %s\n", r->str ? r->str : "(no msg)");
    return false;
  }
  return true;
}

bool RedisClient::commandStatusIs_(redisReply* r, const char* expect) {
  if (!r) { std::fprintf(stderr, "[redis] null status reply\n"); return false; }
  if (r->type == REDIS_REPLY_STATUS && r->str && std::string(r->str) == expect) return true;
  std::fprintf(stderr, "[redis] bad status: type=%d str=%s expect=%s\n",
               r->type, r->str ? r->str : "(null)", expect);
  return false;
}

bool RedisClient::expire_(const std::string& key, int ttl_sec) {
  if (ttl_sec <= 0) return true;
  redisReply* r = (redisReply*)redisCommand(ctx_, "EXPIRE %s %d", key.c_str(), ttl_sec);
  bool ok = commandOk_(r);
  if (r) freeReplyObject(r);
  return ok;
}

bool RedisClient::readLastTickHash(const std::string& hash_key_prefix,
                                   const std::string& inst,
                                   double& last, double& bid1, double& ask1,
                                   int64_t& ts_ms) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;
  // 若上次开启过 pipeline，先清空挂起回复，避免污染本次读
  flushPendingLocked_();

  char key[256]; std::snprintf(key, sizeof(key), "%s%s", hash_key_prefix.c_str(), inst.c_str());
  redisReply* r = (redisReply*)redisCommand(ctx_, "HMGET %s last bid1 ask1 ts", key);
  if (!r || r->type != REDIS_REPLY_ARRAY || r->elements < 4) { if (r) freeReplyObject(r); return false; }

  auto f = [&](size_t i, double& out)->bool{
    if (!r->element[i] || r->element[i]->type != REDIS_REPLY_STRING) return false;
    out = std::atof(r->element[i]->str); return true;
  };
  auto g = [&](size_t i, int64_t& out)->bool{
    if (!r->element[i] || r->element[i]->type != REDIS_REPLY_STRING) return false;
    out = std::atoll(r->element[i]->str); return true;
  };

  bool ok = f(0, last) && f(1, bid1) && f(2, ask1) && g(3, ts_ms);
  freeReplyObject(r);
  return ok;
}

bool RedisClient::writeTradeEvent(const std::string& stream_key,
                                  const std::string& strategy,
                                  const std::string& phase,
                                  const std::string& text,
                                  const std::string& order_ref,
                                  const std::string& inst,
                                  int64_t ts_ms) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;
  // 事件通常不走 pipeline，直接写
  redisReply* r = (redisReply*)redisCommand(ctx_,
      "XADD %s * strat %s phase %s text %s ref %s inst %s ts %lld",
      stream_key.c_str(), strategy.c_str(), phase.c_str(), text.c_str(),
      order_ref.c_str(), inst.c_str(), (long long)ts_ms);
  bool ok = commandOk_(r); if (r) freeReplyObject(r);
  return ok;
}

bool RedisClient::writeTradeHash(const std::string& hash_key_prefix,
                                 const std::string& order_ref,
                                 const std::string& strategy,
                                 const std::string& phase,
                                 const std::string& text,
                                 const std::string& inst,
                                 int64_t ts_ms, int ttl_sec) {
  std::lock_guard<std::mutex> lk(mtx_);
  if (!ctx_) return false;

  char key[256]; std::snprintf(key, sizeof(key), "%s%s", hash_key_prefix.c_str(), order_ref.c_str());

  if (!pipeline_) {
    redisReply* r = (redisReply*)redisCommand(ctx_,
        "HSET %s strat %s phase %s text %s inst %s ts %lld",
        key, strategy.c_str(), phase.c_str(), text.c_str(), inst.c_str(), (long long)ts_ms);
    bool ok = commandOk_(r); if (r) freeReplyObject(r);
    if (ok && ttl_sec > 0) ok = expire_(key, ttl_sec);
    return ok;
  }

  if (redisAppendCommand(ctx_, "HSET %s strat %s phase %s text %s inst %s ts %lld",
                         key, strategy.c_str(), phase.c_str(), text.c_str(),
                         inst.c_str(), (long long)ts_ms) == REDIS_OK) ++pending_;
  if (ttl_sec > 0) { if (redisAppendCommand(ctx_, "EXPIRE %s %d", key, ttl_sec) == REDIS_OK) ++pending_; }
  if (pipe_window_ > 0 && pending_ >= pipe_window_) return flushPendingLocked_();
  return true;
}