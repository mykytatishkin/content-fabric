#pragma once

#include <iostream>
#include <string>
#include <cstdio>

#ifdef VIDEO_TOOL_ENABLE_LOGGING
#include <spdlog/spdlog.h>
#define LOG_INFO(...) spdlog::info(__VA_ARGS__)
#define LOG_WARN(...) spdlog::warn(__VA_ARGS__)
#define LOG_ERROR(...) spdlog::error(__VA_ARGS__)
#else
#define LOG_INFO(...) do { std::cerr << "[INFO] "; std::fprintf(stderr, __VA_ARGS__); std::cerr << "\n"; } while(0)
#define LOG_WARN(...) do { std::cerr << "[WARN] "; std::fprintf(stderr, __VA_ARGS__); std::cerr << "\n"; } while(0)
#define LOG_ERROR(...) do { std::cerr << "[ERROR] "; std::fprintf(stderr, __VA_ARGS__); std::cerr << "\n"; } while(0)
#endif

