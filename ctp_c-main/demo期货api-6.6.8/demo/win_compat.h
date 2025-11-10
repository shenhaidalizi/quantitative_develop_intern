// 覆盖 /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/win_compat.h
#pragma once
#ifndef _WIN32
#include <unistd.h>
#include <termios.h>
#include <sys/time.h>
#include <sys/syscall.h>
#include <pthread.h>
#include <condition_variable>
#include <mutex>
#include <chrono>
#include <stdint.h>
#include <time.h>
#include <fcntl.h>       // <- 必须：open/O_RDONLY
#include <cstdio>

#define INFINITE 0xFFFFFFFF

struct WinCompatEvent {
  std::mutex m; std::condition_variable cv; bool signaled; bool manual;
  explicit WinCompatEvent(bool manual_reset, bool initial_state)
      : signaled(initial_state), manual(manual_reset) {}
};
using HANDLE = WinCompatEvent*;

static inline HANDLE CreateEvent(void*, bool manual_reset, bool initial_state, const char*) { return new WinCompatEvent(manual_reset, initial_state); }
static inline void SetEvent(HANDLE h){ std::unique_lock<std::mutex> lk(h->m); h->signaled = true; if (h->manual) h->cv.notify_all(); else h->cv.notify_one(); }
static inline void ResetEvent(HANDLE h){ std::unique_lock<std::mutex> lk(h->m); h->signaled = false; }
static inline unsigned long WaitForSingleObject(HANDLE h, unsigned long ms){
  std::unique_lock<std::mutex> lk(h->m);
  if (ms == INFINITE) { h->cv.wait(lk, [&]{ return h->signaled; }); }
  else if (!h->cv.wait_for(lk, std::chrono::milliseconds(ms), [&]{ return h->signaled; })) return 1;
  if (!h->manual) h->signaled = false;
  return 0;
}
static inline void CloseHandle(HANDLE h){ delete h; }
static inline void Sleep(unsigned long ms){ usleep(ms * 1000); }

// 阻塞版 _getch：交互终端等待按键；非 TTY 则常驻不退出
static inline int _getch() {
  int fd = isatty(STDIN_FILENO) ? STDIN_FILENO : open("/dev/tty", O_RDONLY);
  if (fd == -1) { for(;;) Sleep(1000); } // 无 TTY：保持常驻
  termios oldt{}, newt{};
  if (tcgetattr(fd, &oldt) != 0) { if (fd != STDIN_FILENO) close(fd); for(;;) Sleep(1000); }
  newt = oldt; newt.c_lflag &= ~(ICANON | ECHO);
  tcsetattr(fd, TCSANOW, &newt);
  unsigned char ch = 0;
  ssize_t n = read(fd, &ch, 1); // 阻塞等待1字节
  tcsetattr(fd, TCSANOW, &oldt);
  if (fd != STDIN_FILENO) close(fd);
  return n == 1 ? ch : '\n';
}

// Windows 时间/线程ID 兼容
typedef uint16_t WORD;
typedef struct _SYSTEMTIME { WORD wYear,wMonth,wDayOfWeek,wDay,wHour,wMinute,wSecond,wMilliseconds; } SYSTEMTIME;
static inline void GetLocalTime(SYSTEMTIME* st){
  struct timespec ts; clock_gettime(CLOCK_REALTIME, &ts);
  time_t t = ts.tv_sec; struct tm tmv; localtime_r(&t, &tmv);
  st->wYear = (WORD)(tmv.tm_year + 1900); st->wMonth = (WORD)(tmv.tm_mon + 1);
  st->wDayOfWeek = (WORD)tmv.tm_wday; st->wDay = (WORD)tmv.tm_mday;
  st->wHour = (WORD)tmv.tm_hour; st->wMinute = (WORD)tmv.tm_min; st->wSecond = (WORD)tmv.tm_sec;
  st->wMilliseconds = (WORD)(ts.tv_nsec / 1000000);
}
static inline unsigned long GetCurrentThreadId(){
#ifdef SYS_gettid
  return (unsigned long)syscall(SYS_gettid);
#else
  return (unsigned long)pthread_self();
#endif
}
#endif