#pragma once

#include "IVideoOperation.hpp"
#include <nlohmann/json.hpp>

namespace operations {

class ISubtitleTranslator {
public:
    virtual ~ISubtitleTranslator() = default;
    virtual std::string translate(const std::string& text, const std::string& src, const std::string& dst) = 0;
};

class StubSubtitleTranslator : public ISubtitleTranslator {
public:
    std::string translate(const std::string& text, const std::string& src, const std::string& dst) override;
};

class SubtitleTranslateOperation : public IVideoOperation {
public:
    explicit SubtitleTranslateOperation(const nlohmann::json& params);
    void prepare(core::VideoContext& ctx) override;
    void processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t pts) override;
    void finalize(core::VideoContext& ctx) override;

private:
    std::string srcLang_;
    std::string dstLang_;
    std::unique_ptr<ISubtitleTranslator> translator_;
};

} // namespace operations
