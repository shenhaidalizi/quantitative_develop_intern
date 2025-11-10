// 覆盖文件: /home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/timing.h
#pragma once
#ifdef _WIN32
#include <windows.h>
class timing {
public:
  timing() { QueryPerformanceFrequency(&CPU_frequence); }
  ~timing() = default;
  void start() { QueryPerformanceCounter(&time_begin); }
  void end() {
    QueryPerformanceCounter(&time_end);
    gettime = (static_cast<double>(time_end.QuadPart) - static_cast<double>(time_begin.QuadPart))
              / static_cast<double>(CPU_frequence.QuadPart);
  }
  double gettime{};
private:
  LARGE_INTEGER time_begin{}, time_end{}, CPU_frequence{};
};
#else
#include <timing.h>
class timing {
public:
  timing() = default;
  ~timing() = default;
  void start() { clock_gettime(CLOCK_MONOTONIC, &tb); }
  void end() {
    clock_gettime(CLOCK_MONOTONIC, &te);
    gettime = (te.tv_sec - tb.tv_sec) + (te.tv_nsec - tb.tv_nsec) / 1e9;
  }
  double gettime{};
private:
  timespec tb{}, te{};
};
#endif