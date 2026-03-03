#include "SubtitleAdapter.hpp"
#include "../utils/Logging.hpp"

namespace adapters {

core::SubtitleTrack SubtitleAdapter::readSubtitles(core::VideoContext& ctx) {
    core::SubtitleTrack track;
    if (ctx.subtitleStreamIndex < 0) {
        return track;
    }
    // Stub: populate with dummy subtitles
    track.language = "und";
    track.cues.push_back({0, 2000, "Hello"});
    track.cues.push_back({2500, 4000, "World"});
    return track;
}

void SubtitleAdapter::writeSubtitles(core::VideoContext& ctx) {
    (void)ctx; // Stub: write subtitles into output container
}

void SubtitleAdapter::removeSubtitleStream(core::VideoContext& ctx) {
    ctx.subtitleStreamIndex = -1;
}

} // namespace adapters
