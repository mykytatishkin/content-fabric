#pragma once

#include "../core/VideoContext.hpp"
#include <string>

namespace adapters {

class TtsClient {
public:
    TtsClient(std::string baseUrl, std::string apiKey);
    core::AudioData synthesize(const core::SubtitleTrack& subs, const std::string& lang);

private:
    std::string baseUrl_;
    std::string apiKey_;
};

} // namespace adapters
