#pragma once

#include "IVideoOperation.hpp"
#include <nlohmann/json.hpp>
#include <vector>

namespace operations {

struct WatermarkRegion {
    int x{0};
    int y{0};
    int width{0};
    int height{0};
    std::string method{"blur"};
};

class WatermarkRemoveOperation : public IVideoOperation {
public:
    explicit WatermarkRemoveOperation(const nlohmann::json& params);
    void prepare(core::VideoContext& ctx) override;
    void processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t pts) override;
    void finalize(core::VideoContext& ctx) override;

private:
    std::vector<WatermarkRegion> regions_;
    void apply(cv::Mat& img);
};

} // namespace operations
