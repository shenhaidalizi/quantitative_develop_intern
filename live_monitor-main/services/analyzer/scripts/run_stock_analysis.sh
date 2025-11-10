#!/bin/bash

# 股票分析自动化运行脚本
# 作者: 自动生成
# 用途: 按顺序运行数据预处理和实时数据分析

set -e  # 遇到错误立即退出

DIR=$(dirname "$0") 
source $DIR/setup_env.sh

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# PID文件路径
TIMELY_PID_FILE="$DIR/timely_data.pid"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查Python是否可用
check_python() {
    if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        log_error "Python未找到，请确保Python已安装"
        exit 1
    fi
    
    # 优先使用python3，如果没有则使用python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi
    
    log_info "使用Python命令: $PYTHON_CMD"
}

# 检查文件是否存在
check_files() {
    if [ ! -f "preprocess_data.py" ]; then
        log_error "文件 preprocess_data.py 不存在"
        exit 1
    fi
    
    if [ ! -f "timely_data.py" ]; then
        log_error "文件 timely_data.py 不存在"
        exit 1
    fi
    
    log_success "所有必需文件检查完成"
}

# 检查timely_data.py是否在运行
check_timely_status() {
    local pid
    local is_running=false
    
    # 方法1: 检查PID文件
    if [ -f "$TIMELY_PID_FILE" ]; then
        pid=$(cat "$TIMELY_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            if ps -p "$pid" -o cmd= | grep -q "timely_data.py"; then
                log_info "timely_data.py 正在运行 (PID: $pid)"
                is_running=true
            else
                log_warning "PID文件存在但进程已变更，清理PID文件"
                rm -f "$TIMELY_PID_FILE"
            fi
        else
            log_warning "PID文件存在但进程不存在，清理PID文件"
            rm -f "$TIMELY_PID_FILE"
        fi
    fi
    
    # 方法2: 搜索进程
    if [ "$is_running" = false ]; then
        pid=$(pgrep -f "timely_data.py" 2>/dev/null | head -n 1)
        if [ -n "$pid" ]; then
            log_info "找到运行中的 timely_data.py 进程 (PID: $pid)"
            echo "$pid" > "$TIMELY_PID_FILE"
            is_running=true
        fi
    fi
    
    if [ "$is_running" = false ]; then
        log_info "timely_data.py 未运行"
        return 1
    else
        return 0
    fi
}

# 停止timely_data.py进程
stop_timely_data() {
    log_info "正在停止 timely_data.py 进程..."
    
    local pid
    local stopped=false
    
    # 方法1: 通过PID文件停止
    if [ -f "$TIMELY_PID_FILE" ]; then
        pid=$(cat "$TIMELY_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            log_info "通过PID文件停止进程 (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            
            # 等待进程优雅退出
            for i in {1..10}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    log_success "进程已优雅停止"
                    stopped=true
                    break
                fi
                sleep 1
            done
            
            # 如果还没停止，强制杀死
            if [ "$stopped" = false ] && ps -p "$pid" > /dev/null 2>&1; then
                log_warning "优雅停止失败，强制停止进程"
                kill -9 "$pid" 2>/dev/null || true
                sleep 2
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    stopped=true
                fi
            fi
        fi
        rm -f "$TIMELY_PID_FILE"
    fi
    
    # 方法2: 搜索并停止所有相关进程
    if [ "$stopped" = false ]; then
        local pids
        pids=$(pgrep -f "timely_data.py" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            log_info "通过进程搜索停止相关进程"
            echo "$pids" | while read -r pid; do
                if [ -n "$pid" ]; then
                    log_info "停止进程 PID: $pid"
                    kill "$pid" 2>/dev/null || true
                fi
            done
            
            # 等待进程停止
            sleep 3
            
            # 检查是否还有进程
            pids=$(pgrep -f "timely_data.py" 2>/dev/null || true)
            if [ -n "$pids" ]; then
                log_warning "优雅停止失败，强制停止所有相关进程"
                echo "$pids" | while read -r pid; do
                    if [ -n "$pid" ]; then
                        kill -9 "$pid" 2>/dev/null || true
                    fi
                done
                sleep 2
            fi
            stopped=true
        fi
    fi
    
    # 最终检查
    if pgrep -f "timely_data.py" > /dev/null 2>&1; then
        log_error "无法停止 timely_data.py 进程"
        return 1
    else
        log_success "timely_data.py 进程已停止"
        return 0
    fi
}

# 运行数据预处理
run_preprocess() {
    log_info "开始运行数据预处理..."
    log_info "执行命令: $PYTHON_CMD preprocess_data.py"
    
    # 记录开始时间
    start_time=$(date +%s)
    
    # 运行预处理脚本
    if $PYTHON_CMD preprocess_data.py; then
        # 计算运行时间
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_success "数据预处理完成！用时: ${duration}秒"
        return 0
    else
        log_error "数据预处理失败！"
        return 1
    fi
}

# 运行实时数据分析
run_timely_data() {
    log_info "开始运行实时数据分析..."
    log_info "执行命令: $PYTHON_CMD timely_data.py"
    log_warning "注意: 实时数据分析将持续运行，按 Ctrl+C 停止"
    
    # 等待用户确认
    read -p "按回车键继续运行实时数据分析，或按Ctrl+C退出..." -r
    
    # 运行实时数据分析（这个会一直运行）
    $PYTHON_CMD timely_data.py
}

# 后台运行实时数据分析
run_timely_data_daemon() {
    log_info "后台启动实时数据分析..."
    
    # 检查是否已经在运行
    if check_timely_status; then
        log_warning "timely_data.py 已经在运行，请先停止"
        return 1
    fi
    
    # 后台运行并保存PID
    nohup $PYTHON_CMD timely_data.py > ~/logs/timely_data.log 2>&1 &
    local pid=$!
    echo "$pid" > "$TIMELY_PID_FILE"
    
    # 等待一下确保进程启动
    sleep 2
    
    if ps -p "$pid" > /dev/null 2>&1; then
        log_success "timely_data.py 已在后台启动 (PID: $pid)"
        log_info "日志文件: ~/logs/timely_data.log"
        log_info "停止服务: $0 --stop-timely"
        return 0
    else
        log_error "启动失败"
        rm -f "$TIMELY_PID_FILE"
        return 1
    fi
}

# 清理函数（当脚本被中断时调用）
cleanup() {
    log_warning "脚本被中断"
    log_info "正在清理..."
    # 这里可以添加清理逻辑
    exit 0
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 主函数
main() {
    echo "=========================================="
    echo "        股票分析自动化运行脚本"
    echo "=========================================="
    
    log_info "脚本启动"
    
    # 检查环境
    check_python
    check_files
    
    echo ""
    echo "运行计划:"
    echo "1. 运行数据预处理 (preprocess_data.py)"
    echo "2. 运行实时数据分析 (timely_data.py)"
    echo ""
    
    # 询问是否继续
    read -p "是否继续执行? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "用户取消执行"
        exit 0
    fi
    
    echo ""
    log_info "开始执行股票分析流程..."
    
    # 步骤1: 运行数据预处理
    echo ""
    echo "=================== 步骤 1/2 ==================="
    if ! run_preprocess; then
        log_error "数据预处理失败，停止执行"
        exit 1
    fi
    
    # 步骤2: 运行实时数据分析
    echo ""
    echo "=================== 步骤 2/2 ==================="
    run_timely_data
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help        显示帮助信息"
    echo "  --preprocess      仅运行数据预处理"
    echo "  --timely          仅运行实时数据分析"
    echo "  --start-timely    后台启动实时数据分析"
    echo "  --stop-timely     停止实时数据分析"
    echo "  --status          检查实时数据分析状态"
    echo "  --restart-timely  重启实时数据分析"
    echo "  --no-prompt       不显示确认提示，直接运行"
    echo ""
    echo "示例:"
    echo "  $0                     # 运行完整流程"
    echo "  $0 --preprocess        # 仅运行数据预处理"
    echo "  $0 --timely            # 仅运行实时数据分析"
    echo "  $0 --start-timely      # 后台启动实时数据分析"
    echo "  $0 --stop-timely       # 停止实时数据分析"
    echo "  $0 --status            # 检查状态"
    echo "  $0 --restart-timely    # 重启实时数据分析"
    echo "  $0 --no-prompt         # 直接运行，不显示提示"
}

# 解析命令行参数
NO_PROMPT=false
ONLY_PREPROCESS=false
ONLY_TIMELY=false
START_TIMELY=false
STOP_TIMELY=false
CHECK_STATUS=false
RESTART_TIMELY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --preprocess)
            ONLY_PREPROCESS=true
            shift
            ;;
        --timely)
            ONLY_TIMELY=true
            shift
            ;;
        --start-timely)
            START_TIMELY=true
            shift
            ;;
        --stop-timely)
            STOP_TIMELY=true
            shift
            ;;
        --status)
            CHECK_STATUS=true
            shift
            ;;
        --restart-timely)
            RESTART_TIMELY=true
            shift
            ;;
        --no-prompt)
            NO_PROMPT=true
            shift
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 根据参数执行不同逻辑
if [[ "$CHECK_STATUS" == true ]]; then
    check_python
    if check_timely_status; then
        exit 0
    else
        exit 1
    fi
elif [[ "$STOP_TIMELY" == true ]]; then
    stop_timely_data
elif [[ "$START_TIMELY" == true ]]; then
    check_python
    check_files
    run_timely_data_daemon
elif [[ "$RESTART_TIMELY" == true ]]; then
    check_python
    check_files
    log_info "重启 timely_data.py 服务..."
    stop_timely_data
    sleep 2
    run_timely_data_daemon
elif [[ "$ONLY_PREPROCESS" == true ]]; then
    check_python
    check_files
    run_preprocess
elif [[ "$ONLY_TIMELY" == true ]]; then
    check_python
    check_files
    run_timely_data
else
    # 如果设置了 --no-prompt，则修改主函数的提示行为
    if [[ "$NO_PROMPT" == true ]]; then
        # 重新定义主函数，去掉交互式提示
        main_no_prompt() {
            echo "=========================================="
            echo "        股票分析自动化运行脚本"
            echo "=========================================="
            
            log_info "脚本启动 (无提示模式)"
            
            check_python
            check_files
            
            log_info "开始执行股票分析流程..."
            
            echo ""
            echo "=================== 步骤 1/2 ==================="
            if ! run_preprocess; then
                log_error "数据预处理失败，停止执行"
                exit 1
            fi
            
            echo ""
            echo "=================== 步骤 2/2 ==================="
            log_info "开始运行实时数据分析..."
            log_info "执行命令: $PYTHON_CMD timely_data.py"
            log_warning "注意: 实时数据分析将持续运行，按 Ctrl+C 停止"
            
            $PYTHON_CMD timely_data.py
        }
        main_no_prompt
    else
        main
    fi
fi 