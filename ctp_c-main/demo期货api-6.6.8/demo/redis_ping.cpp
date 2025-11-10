// /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_ping.cpp
#include <hiredis/hiredis.h>
#include <cstdio>
int main() {
  const char* host = "192.168.10.12";
  int port = 6381;
  const char* user = "teamPublic_write";
  const char* pass = "f2f71a01";

  timeval timeout{2,0};
  redisContext* c = redisConnectWithTimeout(host, port, timeout);
  if (!c || c->err) { std::printf("connect fail: %s\n", c ? c->errstr : "null"); return 1; }

  redisReply* r = (redisReply*)redisCommand(c, "AUTH %s %s", user, pass);
  if (!r || r->type == REDIS_REPLY_ERROR) { std::printf("auth fail\n"); if (r) freeReplyObject(r); redisFree(c); return 2; }
  freeReplyObject(r);

  r = (redisReply*)redisCommand(c, "PING");
  if (!r) { std::printf("ping null\n"); redisFree(c); return 3; }
  std::printf("PING -> %s\n", (r->type == REDIS_REPLY_STATUS || r->type == REDIS_REPLY_STRING) ? r->str : "(bad)");
  freeReplyObject(r);
  redisFree(c);
  return 0;
}