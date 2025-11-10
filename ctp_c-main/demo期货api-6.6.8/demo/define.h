// 覆盖 /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/define.h
#pragma once
#include <stdio.h>
#include <utility>

extern FILE *logfile;

// 仅字符串（无需格式）
inline void LOG(const char *s) {
    fprintf(logfile, "%s", s);
    printf("%s", s);
    fflush(logfile);
}

// 带格式化参数
template <typename... Args>
inline void LOG(const char *fmt, Args&&... args) {
    fprintf(logfile, fmt, std::forward<Args>(args)...);
    printf(fmt, std::forward<Args>(args)...);
    fflush(logfile);
}