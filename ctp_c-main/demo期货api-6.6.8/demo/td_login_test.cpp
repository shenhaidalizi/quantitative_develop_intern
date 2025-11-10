// /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/td_login_test.cpp
#include <cstdio>
#include <cstring>
#include <string>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <sys/stat.h>
#include <unistd.h>

#include "ThostFtdcTraderApi.h"

static int ensure_dir(const char* p) {
  if (!p || !*p) return -1;
  std::string s(p);
  for (size_t i = 1; i < s.size(); ++i) if (s[i] == '/') ::mkdir(s.substr(0, i).c_str(), 0755);
  ::mkdir(s.c_str(), 0755);
  return access(s.c_str(), W_OK);
}

static std::atomic<int> g_ready{0};
static std::mutex g_m;
static std::condition_variable g_cv;

class TdSpiTest : public CThostFtdcTraderSpi {
public:
  TdSpiTest(CThostFtdcTraderApi* api,
            const char* broker, const char* user, const char* pass,
            const char* app, const char* auth)
  : api_(api) {
    std::strncpy(broker_, broker?broker:"", sizeof(broker_)-1);
    std::strncpy(user_,   user?user:"",     sizeof(user_)-1);
    std::strncpy(pass_,   pass?pass:"",     sizeof(pass_)-1);
    std::strncpy(app_,    app?app:"",       sizeof(app_)-1);
    std::strncpy(auth_,   auth?auth:"",     sizeof(auth_)-1);
  }

  void OnFrontConnected() override {
    std::printf("<Td OnFrontConnected>\n");
    if (app_[0] && auth_[0]) {
      CThostFtdcReqAuthenticateField a{};
      std::strncpy(a.BrokerID, broker_, sizeof(a.BrokerID)-1);
      std::strncpy(a.UserID,   user_,   sizeof(a.UserID)-1);
      std::strncpy(a.AppID,    app_,    sizeof(a.AppID)-1);
      std::strncpy(a.AuthCode, auth_,   sizeof(a.AuthCode)-1);
      logx("<Td OnFrontConnected>");
      log_hex("BrokerID", broker_);
      log_hex("UserID",   user_);
      log_hex("AppID",    app_);
      log_hex("AuthCode", auth_);
      int rc = api_->ReqAuthenticate(&a, 1);
      std::printf("<Td ReqAuthenticate rc=%d>\n", rc);
    } else {
      CThostFtdcReqUserLoginField r{};
      std::strncpy(r.BrokerID, broker_, sizeof(r.BrokerID)-1);
      std::strncpy(r.UserID,   user_,   sizeof(r.UserID)-1);
      std::strncpy(r.Password, pass_,   sizeof(r.Password)-1);
      logx("<Td OnFrontConnected>");
      log_hex("BrokerID", broker_);
      log_hex("UserID",   user_);
      log_hex("Password", pass_);
      int rc = api_->ReqUserLogin(&r, 2);
      std::printf("<Td ReqUserLogin rc=%d>\n", rc);
    }
  }

  void OnFrontDisconnected(int nReason) override {
    std::printf("<Td OnFrontDisconnected> reason=%d\n", nReason);
    g_ready.store(-1); g_cv.notify_all();
  }

  void OnRspAuthenticate(CThostFtdcRspAuthenticateField*, CThostFtdcRspInfoField* e, int, bool) override {
    if (e && e->ErrorID != 0) {
      std::printf("<Td Auth Failed> err=%d\n", e->ErrorID);
      g_ready.store(-2); g_cv.notify_all();
      return;
    }
    std::printf("<Td Auth OK>\n");
    CThostFtdcReqUserLoginField r{};
    std::strncpy(r.BrokerID, broker_, sizeof(r.BrokerID)-1);
    std::strncpy(r.UserID,   user_,   sizeof(r.UserID)-1);
    std::strncpy(r.Password, pass_,   sizeof(r.Password)-1);
    int rc = api_->ReqUserLogin(&r, 3);
    std::printf("<Td ReqUserLogin rc=%d>\n", rc);
  }

  void OnRspUserLogin(CThostFtdcRspUserLoginField* p, CThostFtdcRspInfoField* e, int, bool) override {
    std::printf("<Td OnRspUserLogin>\n");
    if (p) {
      std::printf("  TradingDay=%s FrontID=%d SessionID=%d\n", p->TradingDay, p->FrontID, p->SessionID);
    }
    if (e) std::printf("  ErrorID=%d\n", e->ErrorID);
    if (e && e->ErrorID == 0) { g_ready.store(1); } else { g_ready.store(-3); }
    g_cv.notify_all();
  }

  void OnRspError(CThostFtdcRspInfoField* e, int, bool) override {
    std::printf("<Td RspError> err=%d\n", e ? e->ErrorID : -1);
    g_ready.store(-4); g_cv.notify_all();
  }

private:
  CThostFtdcTraderApi* api_;
  char broker_[32]{}, user_[32]{}, pass_[64]{}, app_[64]{}, auth_[64]{};
};

int main(int argc, char** argv) {
  if (argc < 6) {
    std::fprintf(stderr, "用法: %s tcp://host:port BrokerID UserID Password AppID(optional) AuthCode(optional)\n", argv[0]);
    return 1;
  }
  const char* front = argv[1];
  const char* broker= argv[2];
  const char* user  = argv[3];
  const char* pass  = argv[4];
  const char* app   = (argc >= 6) ? argv[5] : "";
  const char* auth  = (argc >= 7) ? argv[6] : "";

  const char* flow = std::getenv("CTP_FLOW_DIR_TD");
  if (!flow || !*flow) flow = "/tmp/ctp_flow_td_test";
  if (ensure_dir(flow) != 0) { std::fprintf(stderr, "flow 目录不可写: %s\n", flow); return 2; }

  CThostFtdcTraderApi* api = CThostFtdcTraderApi::CreateFtdcTraderApi(flow);
  TdSpiTest* spi = new TdSpiTest(api, broker, user, pass, app, auth);
  api->RegisterSpi(spi);
  api->SubscribePrivateTopic(THOST_TERT_QUICK);
  api->SubscribePublicTopic(THOST_TERT_QUICK);

  static std::string front_copy;
  front_copy = front;
  api->RegisterFront(const_cast<char*>(front_copy.c_str()));
  api->Init();

  // 等待最多 120s（每秒打印一次状态）
std::unique_lock<std::mutex> lk(g_m);
for (int i = 0; i < 120; ++i) {
    int st = g_ready.load();
    if (st != 0) break;
    std::printf("waiting %ds... state=%d\n", i + 1, st);
    g_cv.wait_for(lk, std::chrono::seconds(1));
}
int st = g_ready.load();
if (st == 0) {
    std::fprintf(stderr, "等待登录超时(120s)\n");
    return 3;
}
std::printf("login_state=%d\n", st);
api->Release();
return (st == 1) ? 0 : 4;
}