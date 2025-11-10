// 新增/覆盖: /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/pyctp_bridge.h
#pragma once
#include "ThostFtdcMdApi.h"
#include "ThostFtdcTraderApi.h"

#ifdef __cplusplus
extern "C" {
#endif
#ifdef __cplusplus
extern "C" {
#endif
int  ctp_redis_set_pipeline(int enabled, int window_cmds);
#ifdef __cplusplus
}
#endif
// 日志/行情/交易回调
typedef void (*log_cb_t)(const char* msg);
typedef void (*md_cb_t)(const char* inst, double last, double bid1, double ask1,
                        long long exch_ts_ms, long long recv_cpp_ms, long long redis_ok_ms);
typedef void (*trade_cb_t)(const char* strategy, const char* phase, const char* text);

// 回调注册
void ctp_set_log_cb(log_cb_t cb);
void ctp_set_md_cb(md_cb_t cb);
void ctp_set_trade_cb(trade_cb_t cb);

// Redis（可选）: host, port, password 可为空, db<0 跳过 SELECT, stream_key 如 "md:ticks"
int  ctp_redis_init(const char* host, int port, const char* password, int db, const char* stream_key);
int  ctp_redis_init_acl(const char* host, int port,
    const char* username, const char* password,
    int db, const char* stream_key);
void ctp_redis_close(void);

// 行情: 启动/等待/订阅/停止
int  ctp_md_start(const char* front, const char* broker_id, const char* user_id, const char* password);
int  ctp_md_ready(void);
int  ctp_md_wait_ready(int timeout_ms);
int  ctp_md_subscribe(const char* instruments_csv); // 用逗号分隔
void ctp_md_stop(void);

// 交易: 启动(可选认证)/下单/撤单/停止
int  ctp_td_start(const char* front, const char* broker_id, const char* user_id, const char* password,
                  const char* app_id, const char* auth_code); // app/auth 可为NULL跳过认证
int  ctp_td_ready(void);
int  ctp_td_wait_ready(int timeout_ms);

// 下单: side 'B'买/'S'卖, offset 'O'开/'C'平, pricetype 'A'市价(AnyPrice)/'L'限价, price 用于限价
// 返回 0 成功（仅代表请求已发出），回报通过 trade_cb 返回
int  ctp_td_place(const char* strategy, const char* instrument, char side, char offset, int volume,
                  char pricetype, double price);

// 撤单: 仅演示按 OrderRef 撤（要求策略先下过单）；instrument/ exchange 留空时尽力匹配
int  ctp_td_cancel(const char* strategy, const char* instrument, const char* exchange, const char* order_ref);

void ctp_td_stop(void);

#ifdef __cplusplus
}
#endif