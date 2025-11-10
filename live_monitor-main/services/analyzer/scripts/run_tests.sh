#!/bin/bash

# 股票分析优化测试脚本

echo "======================================"
echo "股票分析优化功能测试"
echo "======================================"
echo ""

# 激活虚拟环境（如果有的话）
source setup_env.sh

# 设置Python路径
# export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 运行测试
echo "🧪 运行综合测试..."
python test_optimizations.py

TEST_RESULT=$?

echo ""
echo "======================================"
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ 所有测试通过！"
else
    echo "❌ 部分测试失败，请检查输出"
fi
echo "======================================"

exit $TEST_RESULT
