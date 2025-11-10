source /home/ubuntu/pyvenv/tradedata-dev/bin/activate

python /home/ubuntu/TradeNew/live/live_futures/scripts/data_recorder.py \
  -e zxjt \
  -s "IM2509,IF2509" \
  -o /home/ubuntu/output/subscribe/ \
  -c /home/ubuntu/TradeNew/live/live_futures/scripts/brokers.json