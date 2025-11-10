# debug/check_original_vol.py
import json

print("=" * 70)
print("🔍 检查原始 JSON 文件中的 Vol 值")
print("=" * 70)

# 读取原始文件（未修复的）
with open('/home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/test_145900_idx238.json', 'r') as f:
    original_data = json.load(f)

# 读取修复后的文件
with open('/home/ubuntu/TradeNew/live/live_monitor/debug/fixed_json/test_145900_idx238.json', 'r') as f:
    fixed_data = json.load(f)

# 找几个有交易量的股票对比
active_codes = ['000691', '603496', '600629', '002295']

print("\n对比原始和修复后的数据:")
print("=" * 70)

for code in active_codes:
    original = next((item for item in original_data if item['code'] == code), None)
    fixed = next((item for item in fixed_data if item['code'] == code), None)
    
    if original and fixed:
        print(f"\n{code} - {original['Name']}")
        print(f"  原始 Vol: {original['Vol']:,.2f}")
        print(f"  修复 Vol: {fixed['Vol']:,.2f}")
        print(f"  差异倍数: {original['Vol'] / fixed['Vol']:.2f}x" if fixed['Vol'] > 0 else "  修复Vol为0")
        print(f"  原始 rolling_full: {original['rolling_full']}")
        print(f"  修复 rolling_full: {fixed['rolling_full']}")

print("\n" + "=" * 70)
print("💡 如果差异倍数是100，说明修复脚本多除了一次100")
print("💡 如果原始Vol本身就很小，说明timely_data.py已经除以过100了")
print("=" * 70)