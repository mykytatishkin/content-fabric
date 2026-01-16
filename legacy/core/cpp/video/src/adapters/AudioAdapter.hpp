#pragma once

#include "../core/VideoContext.hpp"

namespace adapters {

class AudioAdapter {
public:
    static void replaceAudio(core::VideoContext& ctx, const core::AudioData& audio);
};

} // namespace adapters
