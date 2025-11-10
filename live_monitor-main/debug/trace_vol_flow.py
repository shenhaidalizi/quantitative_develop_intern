import requests

print("=" * 70)
print("🔍 追踪 Vol 数据流")
print("=" * 70)

# 1. 检查 API 原始返回
print("\n1️⃣ API 原始返回:")
try:
    response = requests.get("http://dataapi.trader.com/live/cn/all", timeout=10, proxies={"http":None,"https":None})
    data = response.json()
    
    test_stocks = ['000001', '000002', '600031']
    for item in data['data']:
        if item['Symbol'] in test_stocks:
            print(f"  {item['Symbol']} {item['StockName']}: TradingVolume = {item['T radingVolume']:,}")
except Exception as e:
    print(f"  ❌ 无法获取API数据: {e}")

# 2. 检查保存的JSON
print("\n2️⃣ 保存在 JSON 中的 Vol:")
import json
with open('/home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/test_145900_idx238.json', 'r') as f:
    json_data = json.load(f)

for code in test_stocks:
    item = next((x for x in json_data if x['code'] == code), None)
    if item:
        print(f"  {code} {item['Name']}: Vol = {item['Vol']:,}")

# 3. 计算变化
print("\n3️⃣ 数据变化分析:")
print("  如果 JSON Vol = API TradingVolume，说明没有除以任何数")
print("  如果 JSON Vol = API TradingVolume / 100，说明除以了100")
print("  如果 JSON Vol 是其他值，需要检查代码逻辑")

print("\n" + "=" * 70)