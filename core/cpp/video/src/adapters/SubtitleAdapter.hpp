#pragma once

#include "../core/VideoContext.hpp"

namespace adapters {

class SubtitleAdapter {
public:
    static core::SubtitleTrack readSubtitles(core::VideoContext& ctx);
    static void writeSubtitles(core::VideoContext& ctx);
    static void removeSubtitleStream(core::VideoContext& ctx);
};

} // namespace adapters
