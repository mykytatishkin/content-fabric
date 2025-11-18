#include "AudioAdapter.hpp"
#include "../utils/Logging.hpp"

namespace adapters {

void AudioAdapter::replaceAudio(core::VideoContext& ctx, const core::AudioData& audio) {
    (void)ctx;
    (void)audio;
    LOG_INFO("Replacing audio track with synthesized voiceover ({} bytes)", audio.bytes.size());
}

} // namespace adapters
