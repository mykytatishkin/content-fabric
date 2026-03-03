#pragma once

#include "IVideoOperation.hpp"

namespace operations {

class SubtitleRemoveOperation : public IVideoOperation {
public:
    SubtitleRemoveOperation() = default;
    void prepare(core::VideoContext& ctx) override;
    void processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t pts) override;
    void finalize(core::VideoContext& ctx) override;
};

} // namespace operations
