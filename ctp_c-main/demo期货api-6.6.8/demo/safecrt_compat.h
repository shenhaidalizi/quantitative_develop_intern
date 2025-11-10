// 新增文件: /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/safecrt_compat.h
#pragma once
#ifndef _WIN32
#include <string.h>
#define strcpy_s(dst, src) do { \
  size_t _n = sizeof(dst); \
  if (_n) { strncpy((dst), (src), _n - 1); (dst)[_n - 1] = '\0'; } \
} while (0)
#endif