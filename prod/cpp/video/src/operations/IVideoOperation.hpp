#pragma once

#include <cstdint>
#include "../core/VideoContext.hpp"

namespace operations {

class IVideoOperation {
public:
    virtual ~IVideoOperation() = default;
    virtual void prepare(core::VideoContext& ctx) = 0;
    virtual void processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t pts) = 0;
    virtual void finalize(core::VideoContext& ctx) = 0;
};

} // namespace operations
