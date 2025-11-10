// /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/pyctp_bridge.cpp
#include <string>
#include <vector>
#include <sstream>
#include <cstring>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <unordered_map>
#include <ctime>
#include <cstdio>
#include <cstdlib>
#include <chrono>

#include <sys/stat.h>
#include <unistd.h>

#include "ThostFtdcMdApi.h"
#include "ThostFtdcTraderApi.h"
#include "traderSpi.h"        // 复用你已有的 CTraderSpi（非用户系统信息相关逻辑），其余通过子类覆盖
#include "td_hook.h"          // 交易钩子：traderSpi.cpp 内部调用；这里注册转发给 Python
#include "redis_client.h"     // 仅用已实现好的 RedisClient
#include "pyctp_bridge.h"     // 对外 C 接口声明
#include <iconv.h>

// 全局日志文件（匹配 define.h 的 extern FILE* 声明，防止 undefined/conflict）
FILE* logfile = stdout;

extern "C" void ctp_set_log_file(const char* path) {
  if (!path || !*path) return;
  if (FILE* f = std::fopen(path, "a")) logfile = f;
}

// 小工具
static inline void sanitize_copy(char* dst, size_t cap, const char* src) {
  if (!dst || cap == 0) return;
  dst[0] = '\0';
  if (!src) return;
  // 去掉首尾空白与 \r \n \t（防 CRLF/空格）
  const char* s = src;
  while (*s==' '||*s=='\t'||*s=='\r'||*s=='\n') ++s;
  const char* e = s + std::strlen(s);
  while (e > s && (e[-1]==' '||e[-1]=='\t'||e[-1]=='\r'||e[-1]=='\n')) --e;
  size_t n = (size_t)(e - s);
  if (n >= cap) n = cap - 1;
  std::memcpy(dst, s, n);
  dst[n] = '\0';
}
static void log_hex(const char* name, const char* s) {
  if (!s) { std::fprintf(logfile, "%s=null\n", name); std::fflush(logfile); return; }
  std::fprintf(logfile, "%s(len=%zu) hex:", name, std::strlen(s));
  for (const unsigned char* p = (const unsigned char*)s; *p; ++p) {
    std::fprintf(logfile, " %02X", *p);
  }
  std::fprintf(logfile, "\n"); std::fflush(logfile);
}
static int ensure_dir(const char* p) {
  if (!p || !*p) return -1;
  std::string s(p);
  for (size_t i = 1; i < s.size(); ++i)
    if (s[i] == '/') ::mkdir(s.substr(0, i).c_str(), 0755);
  ::mkdir(s.c_str(), 0755);
  return access(s.c_str(), W_OK);
}
static inline long long now_ms() {
  using namespace std::chrono;
  return duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
}
static std::string gbk_to_utf8(const char* s) {
  if (!s) return {};
  iconv_t cd = iconv_open("UTF-8//IGNORE", "GBK");
  if (cd == (iconv_t)-1) return std::string(s);
  size_t inlen = std::strlen(s);
  size_t outlen = inlen * 3 + 8;
  std::string out; out.resize(outlen);
  char* inbuf = const_cast<char*>(s);
  char* outbuf = out.data();
  size_t outleft = outlen;
  if (iconv(cd, &inbuf, &inlen, &outbuf, &outleft) == (size_t)-1) {
    iconv_close(cd);
    return std::string(s);
  }
  iconv_close(cd);
  out.resize(outlen - outleft);
  return out;
}
static long long exch_ts_ms(const CThostFtdcDepthMarketDataField* md) {
  if (!md) return 0;
  const char* day = (md->ActionDay[0] ? md->ActionDay : md->TradingDay);
  int y=0,m=0,d=0,H=0,M=0,S=0;
  if (std::sscanf(day, "%4d%2d%2d", &y, &m, &d) != 3) return 0;
  if (std::sscanf(md->UpdateTime, "%2d:%2d:%2d", &H, &M, &S) != 3) return 0;
  std::tm tm{};
  tm.tm_year = y - 1900; tm.tm_mon = m - 1; tm.tm_mday = d;
  tm.tm_hour = H; tm.tm_min = M; tm.tm_sec = S;
  time_t sec = std::mktime(&tm); if (sec < 0) return 0;
  return (long long)sec * 1000 + (long long)md->UpdateMillisec;
}
// 对 Python 的回调（仅行情/交易；日志回调易崩，log 仅写文件）
static log_cb_t   g_log_cb   = nullptr;
static md_cb_t    g_md_cb    = nullptr;
static trade_cb_t g_trade_cb = nullptr;

static void logx(const char* s) {
  std::fprintf(logfile, "%s\n", s ? s : "");
  std::fflush(logfile);
}

extern "C" void ctp_set_log_cb(log_cb_t cb) { g_log_cb = nullptr; /* 避免从 CTP 线程跨语言回调 */ }
extern "C" void ctp_set_md_cb(md_cb_t cb)   { g_md_cb = cb; }
extern "C" void ctp_set_trade_cb(trade_cb_t cb);

// Redis（复用 your redis_client）
static RedisClient g_redis;
static std::string g_str_prefix  = (std::getenv("REDIS_STR_PREFIX")  ? std::getenv("REDIS_STR_PREFIX")  : "teamPublic:md:last_json:");
static std::string g_hash_prefix = (std::getenv("REDIS_HASH_PREFIX") ? std::getenv("REDIS_HASH_PREFIX") : "teamPublic:mdh:last:");

extern "C" {
int ctp_redis_init_acl(const char* host, int port,
                       const char* username, const char* password,
                       int db, const char* /*unused*/) {
  return g_redis.connect(host?host:"127.0.0.1", port>0?port:6379,
                         username?username:"", password?password:"", db) ? 0 : -1;
}
int ctp_redis_init(const char* host, int port, const char* password, int db, const char* /*unused*/) {
  return g_redis.connect(host?host:"127.0.0.1", port>0?port:6379, "", password?password:"", db) ? 0 : -1;
}
void ctp_redis_close(void) { g_redis.close(); }
void ctp_redis_set_prefixes(const char* str_prefix, const char* hash_prefix) {
  if (str_prefix && *str_prefix)  g_str_prefix  = str_prefix;
  if (hash_prefix && *hash_prefix) g_hash_prefix = hash_prefix;
}
int ctp_redis_set_pipeline(int enabled, int window_cmds) {
  g_redis.setPipeline(enabled != 0, window_cmds > 0 ? window_cmds : 0);
  return 0;
}
} // extern "C"

// ---------------- 行情（MD） ----------------
static CThostFtdcMdApi* g_md = nullptr;
static std::atomic<int> g_md_ready{0};
static std::mutex g_md_m;
static std::condition_variable g_md_cv;
static char g_md_broker[32]{0}, g_md_user[32]{0}, g_md_pass[64]{0};
static std::string g_md_front_str;

class MdSpiBridge : public CThostFtdcMdSpi {
public:
  explicit MdSpiBridge(CThostFtdcMdApi* api): api_(api) {}
  void OnFrontConnected() override {
    logx("<Md OnFrontConnected>");
    CThostFtdcReqUserLoginField req{};
    std::strncpy(req.BrokerID, g_md_broker, sizeof(req.BrokerID)-1);
    std::strncpy(req.UserID,  g_md_user,   sizeof(req.UserID)-1);
    std::strncpy(req.Password,g_md_pass,   sizeof(req.Password)-1);
    api_->ReqUserLogin(&req, 1);
  }
  void OnFrontDisconnected(int) override {
    logx("<Md OnFrontDisconnected>");
    g_md_ready.store(-1);
    g_md_cv.notify_all();
  }
  void OnRspUserLogin(CThostFtdcRspUserLoginField*, CThostFtdcRspInfoField* e, int, bool) override {
    if (e && e->ErrorID != 0){ logx("<Md Login Failed>"); g_md_ready.store(-1); }
    else { logx("<Md Login OK>"); g_md_ready.store(1); }
    g_md_cv.notify_all();
  }
  void OnRspError(CThostFtdcRspInfoField*, int, bool) override {
    logx("<Md RspError>");
    g_md_ready.store(-1);
    g_md_cv.notify_all();
  }
  void OnRspSubMarketData(CThostFtdcSpecificInstrumentField*, CThostFtdcRspInfoField* e, int, bool) override {
    if (e && e->ErrorID != 0) logx("<SubMD Fail>"); else logx("<SubMD OK>");
  }
  void OnRtnDepthMarketData(CThostFtdcDepthMarketDataField* md) override {
    if (!md) return;
    long long recv_ms  = now_ms();               // C++收到回调时刻(ms)
    long long ex_ms    = exch_ts_ms(md);         // 交易所时间(ms)
    bool ok1 = g_redis.writeTickString(g_str_prefix,  md->InstrumentID, md->LastPrice, md->BidPrice1, md->AskPrice1, recv_ms, 86400);
    bool ok2 = g_redis.writeTickHash  (g_hash_prefix, md->InstrumentID, md->LastPrice, md->BidPrice1, md->AskPrice1, recv_ms, 86400);
    long long redis_ms = (ok1 && ok2) ? now_ms() : 0;  // 写入成功后的时间(ms)，失败则为0
    if (g_md_cb) g_md_cb(md->InstrumentID, md->LastPrice, md->BidPrice1, md->AskPrice1, ex_ms, recv_ms, redis_ms);
  }
private:
  CThostFtdcMdApi* api_;
};

static MdSpiBridge* g_md_spi = nullptr;

extern "C" {
int ctp_md_start(const char* front, const char* broker_id, const char* user_id, const char* password){
  if (g_md) return 0;
  std::strncpy(g_md_broker, broker_id?broker_id:"", sizeof(g_md_broker)-1);
  std::strncpy(g_md_user,   user_id?user_id:"",     sizeof(g_md_user)-1);
  std::strncpy(g_md_pass,   password?password:"",   sizeof(g_md_pass)-1);

  const char* flow = std::getenv("CTP_FLOW_DIR_MD");
  if (!flow || !*flow) flow = std::getenv("CTP_FLOW_DIR");
  if (!flow || !*flow) flow = "/tmp/ctp_flow_md";
  if (ensure_dir(flow) != 0) { g_md_ready.store(-3); return -3; }
  g_md_ready.store(0);

  g_md = CThostFtdcMdApi::CreateFtdcMdApi(flow);
  g_md_spi = new MdSpiBridge(g_md);
  g_md->RegisterSpi(g_md_spi);
  g_md_front_str = front ? front : "";
  g_md->RegisterFront(const_cast<char*>(g_md_front_str.c_str()));
  g_md->Init();
  return 0;
}
int ctp_md_ready(void){ return g_md_ready.load(); }
int ctp_md_wait_ready(int timeout_ms){
  std::unique_lock<std::mutex> lk(g_md_m);
  if (g_md_ready.load() == 1) return 1;
  if (timeout_ms < 0) g_md_cv.wait(lk, []{ return g_md_ready.load()!=0; });
  else if (!g_md_cv.wait_for(lk, std::chrono::milliseconds(timeout_ms), []{ return g_md_ready.load()!=0; })) return 0;
  return g_md_ready.load();
}
static std::vector<std::string> split_csv(const char* csv){
  std::vector<std::string> out; if (!csv) return out; std::stringstream ss(csv); std::string s;
  while (std::getline(ss, s, ',')) if (!s.empty()) out.push_back(s); return out;
}
int ctp_md_subscribe(const char* instruments_csv){
  if (!g_md) return -1; if (g_md_ready.load()!=1) return -2;
  auto v = split_csv(instruments_csv); if (v.empty()) return 0;
  std::vector<char*> ptr; ptr.reserve(v.size()); for (auto& s:v) ptr.push_back(const_cast<char*>(s.c_str()));
  return g_md->SubscribeMarketData(ptr.data(), (int)v.size());
}
void ctp_md_stop(void){
  if (g_md){ g_md->Release(); g_md=nullptr; }
  delete g_md_spi; g_md_spi=nullptr; g_md_ready.store(0);
}
} // extern "C"

// ---------------- 交易（TD） ----------------
static CThostFtdcTraderApi* g_td = nullptr;
static std::atomic<int> g_td_ready{0};
static std::mutex g_td_m; static std::condition_variable g_td_cv;
static char g_td_broker[32]{0}, g_td_user[32]{0}, g_td_pass[64]{0}, g_td_app[64]{0}, g_td_auth[64]{0};
static int g_order_ref = 1;
static std::string g_td_front_str;

struct OrderKey{ std::string strategy, inst, exch, ref; };
static std::unordered_map<std::string, OrderKey> g_ref_map;

// 交易钩子适配：traderSpi.cpp 在各回调尾部调用 td_set_hook，这里将其转给 Python，并更新就绪状态
static void td_hook_adapter(const char* phase, const char* order_ref, const char* inst, const char* text) {
  // 仅转发消息（中文转 UTF-8）；不在此处修改就绪状态
  const char* ref = order_ref ? order_ref : "";
  const char* ph  = phase ? phase : "";
  std::string msg = gbk_to_utf8(text ? text : "");
  if (g_trade_cb) {
    g_trade_cb(ref, ph, msg.c_str());
  }
}

extern "C" void ctp_set_trade_cb(trade_cb_t cb){
  g_trade_cb = cb;
  td_set_hook(td_hook_adapter);
}

// 覆盖 OnFrontConnected/OnRspAuthenticate，禁止用户系统信息上报，仅发起认证/登录
class PyTraderSpi : public CTraderSpi {
public:
  explicit PyTraderSpi(CThostFtdcTraderApi* api) : api_(api) {}

  void OnFrontConnected() override {
    logx("<Td OnFrontConnected>");
    if (g_td_app[0] && g_td_auth[0]) {
      CThostFtdcReqAuthenticateField a{};
      std::strncpy(a.BrokerID, g_td_broker, sizeof(a.BrokerID)-1);
      std::strncpy(a.UserID,   g_td_user,   sizeof(a.UserID)-1);
      std::strncpy(a.AppID,    g_td_app,    sizeof(a.AppID)-1);
      std::strncpy(a.AuthCode, g_td_auth,   sizeof(a.AuthCode)-1);
      api_->ReqAuthenticate(&a, 1);
      logx("<Td ReqAuthenticate>");
    } else {
      CThostFtdcReqUserLoginField r{};
      std::strncpy(r.BrokerID, g_td_broker, sizeof(r.BrokerID)-1);
      std::strncpy(r.UserID,   g_td_user,   sizeof(r.UserID)-1);
      std::strncpy(r.Password, g_td_pass,   sizeof(r.Password)-1);
      api_->ReqUserLogin(&r, 2);
      logx("<Td ReqUserLogin>");
    }
  }

  void OnRspAuthenticate(CThostFtdcRspAuthenticateField*, CThostFtdcRspInfoField* e, int, bool) override {
    if (e && e->ErrorID != 0) {
      logx("<Td Auth Failed>");
      if (e->ErrorMsg[0]) { std::string m = gbk_to_utf8(e->ErrorMsg); logx(m.c_str()); }
      g_td_ready.store(-1); g_td_cv.notify_all();
      if (g_trade_cb) g_trade_cb("", "Auth", "Fail");
      return;
    }
    logx("<Td Auth OK>");
    CThostFtdcReqUserLoginField r{};
    std::strncpy(r.BrokerID, g_td_broker, sizeof(r.BrokerID)-1);
    std::strncpy(r.UserID,   g_td_user,   sizeof(r.UserID)-1);
    std::strncpy(r.Password, g_td_pass,   sizeof(r.Password)-1);
    api_->ReqUserLogin(&r, 3);
    logx("<Td ReqUserLogin>");
  }
  void OnRspUserLogin(CThostFtdcRspUserLoginField* p, CThostFtdcRspInfoField* e, int, bool) override {
    logx("<Td OnRspUserLogin>");
    if (p) {
      char buf[256];
      std::snprintf(buf, sizeof(buf), "TradingDay=%s FrontID=%d SessionID=%d",
                    p->TradingDay, p->FrontID, p->SessionID);
      logx(buf);
    }
    if (e && e->ErrorID != 0) {
      if (e->ErrorMsg[0]) { std::string m = gbk_to_utf8(e->ErrorMsg); logx(m.c_str()); }
      g_td_ready.store(-3);
      if (g_trade_cb) g_trade_cb("", "Login", "Fail");
      g_td_cv.notify_all();
      return;
    }
    CThostFtdcSettlementInfoConfirmField c{};
    std::strncpy(c.BrokerID, g_td_broker, sizeof(c.BrokerID)-1);
    std::strncpy(c.InvestorID, g_td_user, sizeof(c.InvestorID)-1);
    api_->ReqSettlementInfoConfirm(&c, 4);
    logx("<Td ReqSettlementInfoConfirm>");
    if (g_trade_cb) g_trade_cb("", "Confirm", "Req");
  }
  void OnRspSettlementInfoConfirm(CThostFtdcSettlementInfoConfirmField*,
    CThostFtdcRspInfoField* e, int, bool) override {
    if (e && e->ErrorID != 0) {
      logx("<Td Confirm Failed>");
      if (e->ErrorMsg[0]) { std::string m = gbk_to_utf8(e->ErrorMsg); logx(m.c_str()); }
      g_td_ready.store(-4);
      if (g_trade_cb) g_trade_cb("", "Confirm", "Fail");
      g_td_cv.notify_all();
      return;
    }
    logx("<Td Confirm OK>");
    g_td_ready.store(1);
    if (g_trade_cb) g_trade_cb("", "Confirm", "OK");
    g_td_cv.notify_all();
  }
private:
  CThostFtdcTraderApi* api_;
};

extern "C" {
int ctp_td_start(const char* front, const char* broker_id, const char* user_id, const char* password,
                 const char* app_id, const char* auth_code){
  if (g_td) return 0;
  sanitize_copy(g_td_broker, sizeof(g_td_broker), broker_id);
  sanitize_copy(g_td_user,   sizeof(g_td_user),   user_id);
  sanitize_copy(g_td_pass,   sizeof(g_td_pass),   password);
  sanitize_copy(g_td_app,    sizeof(g_td_app),    app_id);
  sanitize_copy(g_td_auth,   sizeof(g_td_auth),   auth_code);

  log_hex("BrokerID", g_td_broker);
  log_hex("UserID",   g_td_user);
  log_hex("Password", g_td_pass);
  log_hex("AppID",    g_td_app);
  log_hex("AuthCode", g_td_auth);

  const char* flow = std::getenv("CTP_FLOW_DIR_TD");
  if (!flow || !*flow) flow = std::getenv("CTP_FLOW_DIR");
  if (!flow || !*flow) flow = "/tmp/ctp_flow_td";
  if (ensure_dir(flow) != 0) { g_td_ready.store(-3); return -3; }
  g_td_ready.store(0);

  g_td = CThostFtdcTraderApi::CreateFtdcTraderApi(flow);
  CTraderSpi* spi = new PyTraderSpi(g_td);
  g_td->RegisterSpi(spi);
  g_td->SubscribePrivateTopic(THOST_TERT_QUICK);
  g_td->SubscribePublicTopic(THOST_TERT_QUICK);

  g_td_front_str = front ? front : "";
  g_td->RegisterFront(const_cast<char*>(g_td_front_str.c_str()));
  g_td->Init();
  return 0;
}
int ctp_td_ready(void){ return g_td_ready.load(); }
int ctp_td_wait_ready(int timeout_ms){
  std::unique_lock<std::mutex> lk(g_td_m);
  if (g_td_ready.load()==1) return 1;
  if (timeout_ms<0) g_td_cv.wait(lk, []{ return g_td_ready.load()!=0; });
  else if (!g_td_cv.wait_for(lk, std::chrono::milliseconds(timeout_ms), []{ return g_td_ready.load()!=0; })) return 0;
  return g_td_ready.load();
}

int ctp_td_place(const char* strategy, const char* instrument, char side, char offset, int volume,
  char pricetype, double price){
if (!g_td) return -1; if (g_td_ready.load()!=1) return -2;
CThostFtdcInputOrderField o{}; std::strncpy(o.BrokerID,g_td_broker,sizeof(o.BrokerID)-1);
std::strncpy(o.InvestorID,g_td_user,sizeof(o.InvestorID)-1);
std::strncpy(o.InstrumentID,instrument?instrument:"",sizeof(o.InstrumentID)-1);
std::snprintf(o.OrderRef, sizeof(o.OrderRef), "%08d", g_order_ref++);
o.Direction = (side=='B'||side=='b')? THOST_FTDC_D_Buy : THOST_FTDC_D_Sell;
o.CombOffsetFlag[0] = (offset=='O'||offset=='o')? THOST_FTDC_OF_Open : THOST_FTDC_OF_Close;
o.CombHedgeFlag[0]  = THOST_FTDC_HF_Speculation;

if (pricetype=='L'||pricetype=='l'){
o.OrderPriceType=THOST_FTDC_OPT_LimitPrice;
o.LimitPrice=(price>0)?price:0;  // 价格必须>0
if (o.LimitPrice<=0) return -15; // 防止字段错误
o.TimeCondition = THOST_FTDC_TC_GFD;
} else {
// 真“市价”普遍不被交易所接受；若仍要发，按 IOC 处理
o.OrderPriceType=THOST_FTDC_OPT_AnyPrice;
o.TimeCondition  = THOST_FTDC_TC_IOC;
}

o.VolumeTotalOriginal = volume>0?volume:1;
o.VolumeCondition = THOST_FTDC_VC_AV;
o.ContingentCondition = THOST_FTDC_CC_Immediately;
o.MinVolume = 1;
o.ForceCloseReason = THOST_FTDC_FCC_NotForceClose;
o.IsAutoSuspend = 0;

int rc = g_td->ReqOrderInsert(&o, 11);
if (g_trade_cb){
char msg[256]; std::snprintf(msg,sizeof(msg),"ReqOrderInsert rc=%d ref=%s inst=%s", rc, o.OrderRef, o.InstrumentID);
g_trade_cb(strategy?strategy:"", "PlaceReq", msg);
}
g_ref_map[o.OrderRef] = OrderKey{ strategy?strategy:"", instrument?instrument:"", "", o.OrderRef };
return rc;
}

int ctp_td_cancel(const char* strategy, const char* instrument, const char* exchange, const char* order_ref){
  if (!g_td) return -1; if (g_td_ready.load()!=1) return -2;
  CThostFtdcInputOrderActionField a{};
  std::strncpy(a.BrokerID,g_td_broker,sizeof(a.BrokerID)-1);
  std::strncpy(a.InvestorID,g_td_user,sizeof(a.InvestorID)-1);
  a.ActionFlag = THOST_FTDC_AF_Delete;
  if (instrument) std::strncpy(a.InstrumentID,instrument,sizeof(a.InstrumentID)-1);
  if (exchange)   std::strncpy(a.ExchangeID,exchange,sizeof(a.ExchangeID)-1);
  if (order_ref)  std::strncpy(a.OrderRef,order_ref,sizeof(a.OrderRef)-1);
  int rc = g_td->ReqOrderAction(&a, 12);
  if (g_trade_cb){
    char msg[256]; std::snprintf(msg,sizeof(msg),"ReqOrderAction rc=%d ref=%s inst=%s", rc, a.OrderRef, a.InstrumentID);
    g_trade_cb(strategy?strategy:"", "CancelReq", msg);
  }
  return rc;
}

void ctp_td_stop(void){
  if (g_td){ g_td->Release(); g_td=nullptr; }
  g_td_ready.store(0); g_ref_map.clear();
}
} // extern "C"