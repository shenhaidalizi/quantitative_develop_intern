// 覆盖 /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client_test.cpp
#include "redis_client.h"
#include <hiredis/hiredis.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cinttypes>
#include <cstring>
#include <string>

static int64_t now_ms() {
  using namespace std::chrono;
  return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}
static const char* envs(const char* k, const char* d){ const char* v=getenv(k); return (v&&*v)?v:d; }
static int envi(const char* k, int d){ const char* v=getenv(k); return (v&&*v)?std::atoi(v):d; }
static bool envb(const char* k, bool d){ const char* v=getenv(k); if(!v||!*v) return d; return (std::strcmp(v,"0")!=0 && strcasecmp(v,"false")!=0); }

struct Cfg {
  const char* host   = envs("REDIS_HOST", "192.168.10.12");
  int         port   = envi("REDIS_PORT", 6381);
  const char* user   = envs("REDIS_USER", "teamPublic_write");
  const char* pass   = envs("REDIS_PASS", "f2f71a01");
  int         db     = envi("REDIS_DB", 0);

  const char* str_prefix  = envs("REDIS_STR_PREFIX",  "teamPublic:md:last_json:");
  const char* hash_prefix = envs("REDIS_HASH_PREFIX", "teamPublic:mdh:last:");
  const char* inst_base   = envs("TEST_INST", "IM2512");
  const char* test_tag    = envs("TEST_TAG",  "bench");   // 避免污染，可设不同前缀
  int         ttl         = envi("TEST_TTL", 300);

  int         N           = envi("BATCH_N", 5000);
  int         window      = envi("BATCH_WINDOW", 1000);   // pipeline 每批条数
  bool        do_set      = envb("WRITE_SET", true);
  bool        do_hash     = envb("WRITE_HASH", true);
  const char* mode        = envs("BATCH_MODE", "client"); // client | pipeline
};

static void print_cfg(const Cfg& c){
  std::printf("cfg host=%s port=%d user=%s db=%d N=%d window=%d mode=%s ttl=%d do_set=%d do_hash=%d\n",
              c.host, c.port, c.user, c.db, c.N, c.window, c.mode, c.ttl, c.do_set?1:0, c.do_hash?1:0);
  std::printf("keys str_prefix=%s hash_prefix=%s inst_base=%s tag=%s\n",
              c.str_prefix, c.hash_prefix, c.inst_base, c.test_tag);
}

static std::string make_inst(const Cfg& c, int i){
  std::string s; s.reserve(64);
  s.append(c.inst_base).append(":").append(c.test_tag).append(":").append(std::to_string(i));
  return s;
}

static int bench_client(const Cfg& cfg){
  RedisClient rc;
  bool okc = rc.connect(cfg.host, cfg.port, cfg.user, cfg.pass, cfg.db);
  std::printf("connect=%d\n", okc?1:0);
  if (!okc) return 1;

  // 预热
  rc.writeTickHash(cfg.hash_prefix, make_inst(cfg, -1), 1,1,1, now_ms(), cfg.ttl);

  int64_t t0 = now_ms();
  long ok_set = 0, ok_hset = 0;
  for (int i=0;i<cfg.N;i++){
    auto inst = make_inst(cfg, i);
    double last = 123.45 + (i%10)*0.01, bid1 = last - 0.05, ask1 = last + 0.05;
    int64_t ts = now_ms();
    if (cfg.do_set)  ok_set  += rc.writeTickString(cfg.str_prefix,  inst, last, bid1, ask1, ts, cfg.ttl) ? 1:0;
    if (cfg.do_hash) ok_hset += rc.writeTickHash  (cfg.hash_prefix, inst, last, bid1, ask1, ts, cfg.ttl) ? 1:0;
  }
  int64_t t1 = now_ms();
  int cmds = (cfg.do_set?1:0) + (cfg.do_hash?1:0);
  double dur_ms = double(t1 - t0);
  double qps = (dur_ms>0) ? (cfg.N*cmds) / (dur_ms/1000.0) : 0.0;

  std::printf("client: wrote=%d recs, cmds/recs=%d, ok_set=%ld ok_hset=%ld, time_ms=%.3f, qps=%.1f cmd/s\n",
              cfg.N, cmds, ok_set, ok_hset, dur_ms, qps);
  return 0;
}

// pipeline 仅用 hiredis 原生接口，避免 wrapper 循环往返
static int bench_pipeline(const Cfg& c){
  timeval timeout{2,0};
  redisContext* ctx = redisConnectWithTimeout(c.host, c.port, timeout);
  if (!ctx || ctx->err){ std::printf("pipe connect fail: %s\n", ctx?ctx->errstr:"null"); if(ctx) redisFree(ctx); return 2; }
  redisReply* r = nullptr;
  if (c.user && *c.user) r = (redisReply*)redisCommand(ctx, "AUTH %s %s", c.user, c.pass);
  else                   r = (redisReply*)redisCommand(ctx, "AUTH %s", c.pass);
  if (!r || r->type == REDIS_REPLY_ERROR){ std::printf("pipe auth fail\n"); if(r) freeReplyObject(r); redisFree(ctx); return 3; }
  if (r) freeReplyObject(r);
  if (c.db >= 0){ r = (redisReply*)redisCommand(ctx,"SELECT %d", c.db); if(r) freeReplyObject(r); }

  int64_t t0 = now_ms();
  long appended = 0, replies = 0, ok = 0;

  auto send_batch = [&](int n)->void{
    // 取回 n 批次内追加的所有回复
    for (int k=0;k<n;k++){
      void* rp = nullptr;
      if (redisGetReply(ctx, &rp) == REDIS_OK && rp){
        redisReply* rr = (redisReply*)rp;
        if (rr->type != REDIS_REPLY_ERROR) ok++;
        freeReplyObject(rr);
      }
      replies++;
    }
  };

  int window = c.window>0 ? c.window : 1000;
  int cmds_per_rec = (c.do_set?2:0) + (c.do_hash?2:0); // 每条记录发两条命令：写+expire
  int cmds_in_window = 0;

  for (int i=0;i<c.N;i++){
    auto inst = make_inst(c, i);
    char key_s[256]; std::snprintf(key_s, sizeof(key_s), "%s%s", c.str_prefix, inst.c_str());
    char key_h[256]; std::snprintf(key_h, sizeof(key_h), "%s%s", c.hash_prefix, inst.c_str());
    double last = 123.45 + (i%10)*0.01, bid1 = last - 0.05, ask1 = last + 0.05;
    int64_t ts = now_ms();

    if (c.do_set){
      char val[512];
      std::snprintf(val, sizeof(val),
        "{\"inst\":\"%s\",\"last\":%.10f,\"bid1\":%.10f,\"ask1\":%.10f,\"ts\":%lld}",
        inst.c_str(), last, bid1, ask1, (long long)ts);
      redisAppendCommand(ctx, "SET %s %s", key_s, val); appended++; cmds_in_window++;
      redisAppendCommand(ctx, "EXPIRE %s %d", key_s, c.ttl); appended++; cmds_in_window++;
    }
    if (c.do_hash){
      redisAppendCommand(ctx, "HSET %s last %.10f bid1 %.10f ask1 %.10f ts %lld",
                         key_h, last, bid1, ask1, (long long)ts); appended++; cmds_in_window++;
      redisAppendCommand(ctx, "EXPIRE %s %d", key_h, c.ttl); appended++; cmds_in_window++;
    }

    if (cmds_in_window >= window*cmds_per_rec){
      send_batch(cmds_in_window);
      cmds_in_window = 0;
    }
  }
  if (cmds_in_window > 0) send_batch(cmds_in_window);

  int64_t t1 = now_ms();
  double dur_ms = double(t1 - t0);
  double qps = (dur_ms>0) ? appended / (dur_ms/1000.0) : 0.0;
  std::printf("pipeline: recs=%d cmds=%ld ok=%ld time_ms=%.3f qps=%.1f cmd/s window=%d\n",
              c.N, appended, ok, dur_ms, qps, window);

  redisFree(ctx);
  return 0;
}

int main(){
  Cfg cfg; print_cfg(cfg);
  if (strcasecmp(cfg.mode, "pipeline")==0) return bench_pipeline(cfg);
  return bench_client(cfg);
}