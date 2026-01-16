#include "VoiceoverReplaceOperation.hpp"
#include "../adapters/TtsClient.hpp"
#include "../adapters/AudioAdapter.hpp"
#include "../utils/Logging.hpp"

namespace operations {

VoiceoverReplaceOperation::VoiceoverReplaceOperation(const nlohmann::json& params) {
    lang_ = params.value("lang", "auto");
    baseUrl_ = params.value("base_url", "");
    apiKey_ = params.value("api_key", "");
}

void VoiceoverReplaceOperation::prepare(core::VideoContext& ctx) {
    adapters::TtsClient client(baseUrl_, apiKey_);
    ctx.generatedVoiceover = client.synthesize(ctx.subtitles, lang_);
}

void VoiceoverReplaceOperation::processFrame(core::VideoContext&, AVFrame*, int64_t) {}

void VoiceoverReplaceOperation::finalize(core::VideoContext& ctx) {
    adapters::AudioAdapter::replaceAudio(ctx, ctx.generatedVoiceover);
}

} // namespace operations
