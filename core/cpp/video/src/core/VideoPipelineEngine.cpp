#include "VideoPipelineEngine.hpp"
#include "../operations/IVideoOperation.hpp"
#include "../operations/SubtitleTranslateOperation.hpp"
#include "../operations/SubtitleRemoveOperation.hpp"
#include "../operations/WatermarkRemoveOperation.hpp"
#include "../operations/VoiceoverReplaceOperation.hpp"
#include "../adapters/FfmpegAdapter.hpp"
#include "../utils/Logging.hpp"

#include <opencv2/imgproc.hpp>

namespace core {

VideoPipelineEngine::VideoPipelineEngine(const VideoJob& job) : job_(job) {}

void VideoPipelineEngine::run() {
    initialize();
    buildOperations();
    processFrames();
    shutdown();
}

void VideoPipelineEngine::initialize() {
    adapters::FfmpegAdapter::openInput(job_.input(), ctx_);
    adapters::FfmpegAdapter::openOutput(job_.output(), ctx_);
}

void VideoPipelineEngine::buildOperations() {
    for (const auto& op : job_.operations()) {
        if (op.type == "subtitles_translate") {
            operations_.push_back(std::make_unique<operations::SubtitleTranslateOperation>(op.params));
        } else if (op.type == "subtitles_remove") {
            operations_.push_back(std::make_unique<operations::SubtitleRemoveOperation>());
        } else if (op.type == "watermark_remove") {
            operations_.push_back(std::make_unique<operations::WatermarkRemoveOperation>(op.params));
        } else if (op.type == "voiceover") {
            operations_.push_back(std::make_unique<operations::VoiceoverReplaceOperation>(op.params));
        } else {
            LOG_WARN("Unknown operation type: {}", op.type);
        }
    }
}

void VideoPipelineEngine::processFrames() {
    for (auto& op : operations_) {
        op->prepare(ctx_);
    }

    AVPacket packet;
    av_init_packet(&packet);
    packet.data = nullptr;
    packet.size = 0;

    while (av_read_frame(ctx_.inputFormat, &packet) >= 0) {
        if (packet.stream_index == ctx_.videoStreamIndex) {
            AVFrame* frame = av_frame_alloc();
            int ret = adapters::FfmpegAdapter::decodeFrame(ctx_, &packet, frame);
            if (ret >= 0) {
                int64_t pts = frame->pts;
                for (auto& op : operations_) {
                    op->processFrame(ctx_, frame, pts);
                }
                adapters::FfmpegAdapter::encodeFrame(ctx_, frame);
            }
            av_frame_free(&frame);
        } else if (packet.stream_index == ctx_.audioStreamIndex) {
            adapters::FfmpegAdapter::copyPacketToOutput(ctx_, &packet);
        }
        av_packet_unref(&packet);
    }

    adapters::FfmpegAdapter::flushEncoder(ctx_);

    for (auto& op : operations_) {
        op->finalize(ctx_);
    }
}

void VideoPipelineEngine::shutdown() {
    adapters::FfmpegAdapter::close(ctx_);
}

} // namespace core
