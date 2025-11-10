// 建议修改一：增强 RedisClient 支持 pipeline（新增 API + 改写写入函数）
// 文件：/home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client.h
#pragma once
#include <string>
#include <mutex>
#include <cstdint>

struct redisContext;
struct redisReply;

class RedisClient {
public:
  RedisClient();
  ~RedisClient();

  bool connect(const std::string& host, int port,
               const std::string& username,
               const std::string& password,
               int db);

  void close();

  // 行情写入
  bool writeTickStream(const std::string& stream_key,
                       const std::string& inst,
                       double last, double bid1, double ask1,
                       int64_t ts_ms);

  // 若未开启 pipeline：每次立即发送并等待回复；若开启 pipeline：仅 append 命令，达阈值自动 flush
  bool writeTickHash(const std::string& hash_key_prefix,
                     const std::string& inst,
                     double last, double bid1, double ask1,
                     int64_t ts_ms, int ttl_sec = -1);

  bool writeTickString(const std::string& string_key_prefix,
                       const std::string& inst,
                       double last, double bid1, double ask1,
                       int64_t ts_ms, int ttl_sec = -1);

  bool readLastTickHash(const std::string& hash_key_prefix,
                        const std::string& inst,
                        double& last, double& bid1, double& ask1,
                        int64_t& ts_ms);

  bool writeTradeEvent(const std::string& stream_key,
                       const std::string& strategy,
                       const std::string& phase,
                       const std::string& text,
                       const std::string& order_ref,
                       const std::string& inst,
                       int64_t ts_ms);

  bool writeTradeHash(const std::string& hash_key_prefix,
                      const std::string& order_ref,
                      const std::string& strategy,
                      const std::string& phase,
                      const std::string& text,
                      const std::string& inst,
                      int64_t ts_ms, int ttl_sec = -1);

  // 新增：pipeline 控制
  void setPipeline(bool enabled, int window_cmds);
  bool flushPipeline();  // 手动 flush 未取回的回复

private:
  bool authAcl_(const std::string& username, const std::string& password);
  bool authLegacy_(const std::string& password);
  bool ping_();
  bool select_(int db);
  bool commandOk_(redisReply* r);
  bool commandStatusIs_(redisReply* r, const char* expect);
  bool expire_(const std::string& key, int ttl_sec);

  // 新增：pipeline 内部
  bool flushPendingLocked_(); // 需持锁调用

private:
  redisContext* ctx_;
  std::mutex mtx_;
  bool pipeline_ = false;  // 是否启用 pipeline
  int  pipe_window_ = 0;   // 达到多少“命令数”时自动 flush
  int  pending_ = 0;       // 未取回的回复条数
};