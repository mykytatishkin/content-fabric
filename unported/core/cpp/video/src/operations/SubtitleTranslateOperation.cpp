#include "SubtitleTranslateOperation.hpp"
#include "../adapters/SubtitleAdapter.hpp"
#include "../utils/Logging.hpp"

namespace operations {

SubtitleTranslateOperation::SubtitleTranslateOperation(const nlohmann::json& params) {
    srcLang_ = params.value("src_lang", "auto");
    dstLang_ = params.value("dst_lang", "auto");
    translator_ = std::make_unique<StubSubtitleTranslator>();
}

std::string StubSubtitleTranslator::translate(const std::string& text, const std::string& src, const std::string& dst) {
    return "[" + dst + "] " + text;
}

void SubtitleTranslateOperation::prepare(core::VideoContext& ctx) {
    ctx.subtitles = adapters::SubtitleAdapter::readSubtitles(ctx);
    for (auto& cue : ctx.subtitles.cues) {
        cue.text = translator_->translate(cue.text, srcLang_, dstLang_);
    }
    ctx.subtitles.language = dstLang_;
}

void SubtitleTranslateOperation::processFrame(core::VideoContext&, AVFrame*, int64_t) {}

void SubtitleTranslateOperation::finalize(core::VideoContext& ctx) {
    adapters::SubtitleAdapter::writeSubtitles(ctx);
}

} // namespace operations
