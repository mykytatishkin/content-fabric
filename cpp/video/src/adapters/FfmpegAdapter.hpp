#pragma once

#include "../core/VideoContext.hpp"
#include <opencv2/core.hpp>

namespace adapters {

class FfmpegAdapter {
public:
    static void openInput(const std::string& path, core::VideoContext& ctx);
    static void openOutput(const std::string& path, core::VideoContext& ctx);
    static int decodeFrame(core::VideoContext& ctx, AVPacket* packet, AVFrame* frame);
    static void encodeFrame(core::VideoContext& ctx, AVFrame* frame);
    static void copyPacketToOutput(core::VideoContext& ctx, AVPacket* packet);
    static void flushEncoder(core::VideoContext& ctx);
    static void close(core::VideoContext& ctx);

    static cv::Mat toMat(AVFrame* frame);
    static void fromMat(const cv::Mat& img, AVFrame* frame);
};

} // namespace adapters
