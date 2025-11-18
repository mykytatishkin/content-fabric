#pragma once

#include "IVideoOperation.hpp"
#include <nlohmann/json.hpp>
#include <memory>

namespace operations {

class VoiceoverReplaceOperation : public IVideoOperation {
public:
    explicit VoiceoverReplaceOperation(const nlohmann::json& params);
    void prepare(core::VideoContext& ctx) override;
    void processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t pts) override;
    void finalize(core::VideoContext& ctx) override;

private:
    std::string lang_;
    std::string baseUrl_;
    std::string apiKey_;
};

} // namespace operations
