# 可选：Python 校验（需要 pip install redis）
import time, json, redis

r = redis.Redis(host='192.168.10.12', port=6381, username='teamPublic_write',
                password='f2f71a01', db=0, decode_responses=True)

print("PING:", r.ping())

k_str = 'teamPublic:md:last_json:IM2512'
k_hash = 'teamPublic:mdh:last:IM2512'

js = r.get(k_str)
h  = r.hgetall(k_hash)
print("GET:", js)
print("HGETALL:", h)

ts = int(h.get('ts', '0'))
print("ts_delta_ms:", int(time.time()*1000) - ts)   # 应接近 0~几千 ms
print("TTL(str):", r.ttl(k_str), "TTL(hash):", r.ttl(k_hash))  # ~86400 且递减

# 连续观察 5 次
for _ in range(5):
    h = r.hgetall(k_hash)
    print("last/bid1/ask1:", h.get('last'), h.get('bid1'), h.get('ask1'))
    time.sleep(1)