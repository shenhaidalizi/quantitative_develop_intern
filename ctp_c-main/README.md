#CTP_C
CTP_C是一个不完全成熟的项目，在之前demo的基础上重写了对应的类和接口或复用了一些接口，完成了初步的订阅和交易功能，简易的example写在test_bridge.py文件中，该文件可以实现订阅并将数据存入redis，下单并将订单信息存入redis。

基本实现在PyCTP Bridge中：
使用C++复用了现有的CTP SPI逻辑，在回调内江行情写入Redis（支持SET/HSET 与 pipeline）,并将关键事件通过C回调接口转发给Python。

线程模型：CTP内部线程驱动回调；日志回调因为避免跨语言线程问题被禁用，有待后续修改；行情和交易回调可安全传递基本类型/稳定指针。

编译依赖：thostmduserapi_se.so、thosttraderapi_se.so、hiredis。

TIP:本项目使用6.6.8版本的.so库，后面的库对该.so库并未兼容，不修改代码的情况下只能进行正常的订阅，而无法进行交易，据推测是传递的参数不正确，但是未在官方文档中找到对应接口，有待后续验证。

核心类：
- MdSpiBridge (CThostFtdcMdSpi)
  - 登录与订阅处理；在 `OnRtnDepthMarketData` 内写入 Redis 两份数据：
    - String: `SET {str_prefix}{inst} {"inst":...,"last":...,"bid1":...,"ask1":...,"ts":recv_ms}`
    - Hash:   `HSET {hash_prefix}{inst} last ... bid1 ... ask1 ... ts recv_ms`
  - 回调给 Python: `md_cb(inst, last, bid1, ask1, exch_ts_ms, recv_cpp_ms, redis_ok_ms)`

- PyTraderSpi (继承自 CTraderSpi)
  - 覆盖 `OnFrontConnected/OnRspAuthenticate/OnRspUserLogin/OnRspSettlementInfoConfirm`
  - 流程：认证(可选) → 登录 → 结算确认 → `g_td_ready=1`
  - 交易事件通过 `td_hook.h` 的 `td_set_hook` 从 `traderSpi.cpp` 统一进入，再适配到 Python 回调

### C 接口（pyctp_bridge.h）

- 日志/回调
  - `void ctp_set_log_file(const char* path)`
  - `void ctp_set_log_cb(log_cb_t cb)`（禁用跨语言回调，调用无效）
  - `void ctp_set_md_cb(md_cb_t cb)`
  - `void ctp_set_trade_cb(trade_cb_t cb)`

- Redis
  - `int  ctp_redis_init(const char* host, int port, const char* password, int db, const char* unused)`
  - `int  ctp_redis_init_acl(const char* host, int port, const char* username, const char* password, int db, const char* unused)`
  - `void ctp_redis_close(void)`
  - `void ctp_redis_set_prefixes(const char* str_prefix, const char* hash_prefix)`
  - `int  ctp_redis_set_pipeline(int enabled, int window_cmds)`
  - 说明：若 Redis 仅允许 `SET/HSET/HGETALL`，则仍可使用；`XADD` 未在桥内调用。TTL 在行情处固定为 86400 秒（可按需更改）。

- 行情（MD）
  - `int  ctp_md_start(const char* front, const char* broker, const char* user, const char* pass)`
  - `int  ctp_md_ready(void)`
  - `int  ctp_md_wait_ready(int timeout_ms)`（<=0 立即返回；>0 超时；<0 一直等）
  - `int  ctp_md_subscribe(const char* instruments_csv)`（逗号分隔）
  - `void ctp_md_stop(void)`

- 交易（TD）
  - `int  ctp_td_start(const char* front, const char* broker, const char* user, const char* pass, const char* app_id, const char* auth_code)`
  - `int  ctp_td_ready(void)`
  - `int  ctp_td_wait_ready(int timeout_ms)`
  - `int  ctp_td_place(const char* strategy, const char* instrument, char side, char offset, int volume, char pricetype, double price)`
    - `side`: 'B' 买 / 'S' 卖
    - `offset`: 'O' 开仓 / 'C' 平仓
    - `pricetype`: 'L' 限价（price>0 必须）/ 'A' 市价（转 IOC）
    - 返回：请求 rc；若限价价差非法返回 -15；成交/拒单在 `trade_cb` 中反馈
  - `int  ctp_td_cancel(const char* strategy, const char* instrument, const char* exchange, const char* order_ref)`
  - `void ctp_td_stop(void)`

### 时延字段

- `exch_ts_ms`: 交易所时间（由 `TradingDay/ActionDay+UpdateTime+UpdateMillisec` 推算）
- `recv_cpp_ms`: C++ 收到回调的系统时间
- `redis_ok_ms`: 成功写入 Redis 后的系统时间（若任一写失败则为 0）

### 常见问题

- Bad format user system info：已通过自定义 `PyTraderSpi` 禁止系统信息上报，避免噪声。
- 结算结果未确认（42）：登录成功后自动发起确认，等确认成功再置 `g_td_ready=1`。
- 报单字段有误（15）：使用限价并保证 `price>0`；Python `ctypes` 单字符参数用 `c_char`。
- Redis NOPERM：改用 `SET/HSET` 并可配置 key 前缀，pipeling 通过 `ctp_redis_set_pipeline` 加速。


### Python 使用要点（ctypes）

- 回调用 `PYFUNCTYPE`；函数原型严格匹配 7 参行情回调与 3 参交易回调。
- 保持回调对象为全局变量，防止 GC。
- 示例流程：初始化 Redis → 设置前缀与 pipeline → 启动 MD/TD → 等待就绪 → 订阅 → 下单/撤单。


编译指令：
python调用的.so
g++ -std=gnu++17 -fPIC \
  /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/pyctp_bridge.cpp \
  /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/traderSpi.cpp \
  /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client.cpp \
  -L/home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo -Wl,-rpath,'$ORIGIN' \
  -l:thostmduserapi_se.so -l:thosttraderapi_se.so -lhiredis -ldl -lpthread \
  -shared -o /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/libpyctp_bridge.so

redis测试文件生成
g++ -std=gnu++17 -O2 \
  /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client_test.cpp \
  /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client.cpp \
  -I/home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo \
  -lhiredis -o /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/redis_client_test




如果重新下载其他版本的问题，注意交易所提供的文件格式，在项目中可以使用如下命令对项目编码进行查看并转换
# 进入文件夹
cd /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo
# 备份一次（仅源码/头文件）
tar czf enc_backup.tgz *.h *.cpp 2>/dev/null || true
# 查看文件格式生成.tsv方便持久化
find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" -o \
                   -name "*.h" -o -name "*.hh" -o -name "*.hpp" -o \
                   -name "*.ini" -o -name "*.cfg" -o -name "*.conf" -o \
                   -name "*.txt" -o -name "*.md" -o -name "*.xml" -o -name "*.json" \) -print0 |
  xargs -0 -I{} sh -c 'enc=$(uchardet "{}"); printf "%s\t%s\n" "$enc" "{}"' \
  > encoding_report.tsv
# 转 GB18030 -> UTF-8
awk -F '\t' '$1=="GB18030"{print $2}' encoding_report.tsv | while read -r f; do
  [ -f "$f" ] || continue
  iconv -f GB18030 -t UTF-8 -c "$f" -o "$f.utf8" && mv "$f.utf8" "$f"
done
# 转 WINDOWS-1252 -> UTF-8（traderApi.cpp）
awk -F '\t' '$1=="WINDOWS-1252"{print $2}' encoding_report.tsv | while read -r f; do
  [ -f "$f" ] || continue
  iconv -f WINDOWS-1252 -t UTF-8 -c "$f" -o "$f.utf8" && mv "$f.utf8" "$f"
done


后续todo:
1.实际上虽然pyctp_bridge中实现的功能很多，但是完全可以拆解并简化，分成md订阅和td交易两个类，让项目结构更清晰一点，目前使用pipeline写入redis实际5000条测试只需100+ms，但是实测从收到数据到打印时间戳需要1000+ms，如果不是交易所抖动的话应该是仍有优化空间。

注：
get_name.py会帮助你从live_future文件中提取出能用的id，该.dat文件由项目live_future生成，执行一次就可以生成对应文件，可以使用这个生成文件获取的id进行合理测试；
api会对各种错误进行返回，返回的errorid数字代表了对应错误信息，错误信息可以在error.xml中进行查询。
另，本项目是从一个windows系统应用demo改过来并进行功能拓展的，所以很多文件似乎可以不用存在，但是我不确定其中的依赖关系所以不进行删除，如果有精力或有时间的话，重写肯定是更好的选择，但是官方文档看起来很简略，可以参考对应ctpwrapper的写法或者直接复用。