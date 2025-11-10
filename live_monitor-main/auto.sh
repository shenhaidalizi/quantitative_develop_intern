#!/bin/bash
set -e  # 遇到错误立即退出

echo "🔹 执行 make down"
make down

echo "🔹 执行 bash scripts/init/setup.sh"
bash scripts/init/setup.sh

echo "🔹 执行 make build"
make build

echo "🔹 执行 make up"
make up

echo "✅ 全部执行完成"
