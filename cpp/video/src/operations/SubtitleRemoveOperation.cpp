#include "SubtitleRemoveOperation.hpp"
#include "../adapters/SubtitleAdapter.hpp"
#include "../utils/Logging.hpp"

namespace operations {

void SubtitleRemoveOperation::prepare(core::VideoContext& ctx) {
    ctx.subtitles.cues.clear();
    ctx.subtitleStreamIndex = -1;
    adapters::SubtitleAdapter::removeSubtitleStream(ctx);
}

void SubtitleRemoveOperation::processFrame(core::VideoContext&, AVFrame*, int64_t) {}

void SubtitleRemoveOperation::finalize(core::VideoContext&) {}

} // namespace operations
