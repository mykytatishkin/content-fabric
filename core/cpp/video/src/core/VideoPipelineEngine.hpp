#pragma once

#include <memory>
#include <vector>
#include "VideoJob.hpp"
#include "VideoContext.hpp"

namespace core {

class VideoPipelineEngine {
public:
    explicit VideoPipelineEngine(const VideoJob& job);
    void run();

private:
    VideoJob job_;
    VideoContext ctx_;
    std::vector<std::unique_ptr<operations::IVideoOperation>> operations_;

    void initialize();
    void buildOperations();
    void processFrames();
    void shutdown();
};

} // namespace core
