#include "TtsClient.hpp"
#include "../utils/Logging.hpp"

#include <curl/curl.h>

namespace adapters {

TtsClient::TtsClient(std::string baseUrl, std::string apiKey)
    : baseUrl_(std::move(baseUrl)), apiKey_(std::move(apiKey)) {}

core::AudioData TtsClient::synthesize(const core::SubtitleTrack& subs, const std::string& lang) {
    (void)subs;
    (void)lang;
    // Stub: perform HTTP request to TTS service. For now, return dummy audio data.
    core::AudioData data;
    data.bytes.assign(1024, 0); // dummy audio payload
    LOG_INFO("Synthesizing voiceover via TTS service at {}", baseUrl_);
    return data;
}

} // namespace adapters
