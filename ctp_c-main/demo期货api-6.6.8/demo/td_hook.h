// 新增文件: /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/td_hook.h
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
typedef void (*td_hook_fn)(const char* phase, const char* order_ref, const char* inst, const char* text);
void td_set_hook(td_hook_fn fn);
#ifdef __cplusplus
}
#endif