#!/bin/bash
# 环境设置脚本

# 加载本地环境配置（如果存在）
if [ -f .env ]; then
    source .env
    source ~/pyvenv/$ENV_NAME/bin/activate
    echo "环境设置完成: $ENV_NAME" 
fi


