#include "FfmpegAdapter.hpp"
#include "../utils/Logging.hpp"

#include <opencv2/imgproc.hpp>
#include <cstring>

namespace adapters {

void FfmpegAdapter::openInput(const std::string& path, core::VideoContext& ctx) {
    if (avformat_open_input(&ctx.inputFormat, path.c_str(), nullptr, nullptr) < 0) {
        throw std::runtime_error("Failed to open input file: " + path);
    }
    avformat_find_stream_info(ctx.inputFormat, nullptr);
    for (unsigned i = 0; i < ctx.inputFormat->nb_streams; ++i) {
        AVStream* stream = ctx.inputFormat->streams[i];
        if (stream->codecpar->codec_type == AVMEDIA_TYPE_VIDEO && ctx.videoStreamIndex < 0) {
            ctx.videoStreamIndex = static_cast<int>(i);
        } else if (stream->codecpar->codec_type == AVMEDIA_TYPE_AUDIO && ctx.audioStreamIndex < 0) {
            ctx.audioStreamIndex = static_cast<int>(i);
        } else if (stream->codecpar->codec_type == AVMEDIA_TYPE_SUBTITLE && ctx.subtitleStreamIndex < 0) {
            ctx.subtitleStreamIndex = static_cast<int>(i);
        }
    }
}

void FfmpegAdapter::openOutput(const std::string& path, core::VideoContext& ctx) {
    avformat_alloc_output_context2(&ctx.outputFormat, nullptr, nullptr, path.c_str());
    if (!ctx.outputFormat) {
        throw std::runtime_error("Failed to create output format context");
    }
}

int FfmpegAdapter::decodeFrame(core::VideoContext& ctx, AVPacket* packet, AVFrame* frame) {
    const AVCodec* codec = avcodec_find_decoder(ctx.inputFormat->streams[ctx.videoStreamIndex]->codecpar->codec_id);
    if (!ctx.videoDecoder) {
        ctx.videoDecoder = avcodec_alloc_context3(codec);
        avcodec_parameters_to_context(ctx.videoDecoder, ctx.inputFormat->streams[ctx.videoStreamIndex]->codecpar);
        avcodec_open2(ctx.videoDecoder, codec, nullptr);
    }
    int ret = avcodec_send_packet(ctx.videoDecoder, packet);
    if (ret < 0) return ret;
    return avcodec_receive_frame(ctx.videoDecoder, frame);
}

void FfmpegAdapter::encodeFrame(core::VideoContext& ctx, AVFrame* frame) {
    (void)ctx;
    (void)frame;
}

void FfmpegAdapter::copyPacketToOutput(core::VideoContext&, AVPacket* packet) {
    (void)packet;
}

void FfmpegAdapter::flushEncoder(core::VideoContext&) {}

void FfmpegAdapter::close(core::VideoContext& ctx) {
    if (ctx.videoDecoder) {
        avcodec_free_context(&ctx.videoDecoder);
    }
    if (ctx.videoEncoder) {
        avcodec_free_context(&ctx.videoEncoder);
    }
    if (ctx.inputFormat) {
        avformat_close_input(&ctx.inputFormat);
    }
    if (ctx.outputFormat) {
        avformat_free_context(ctx.outputFormat);
        ctx.outputFormat = nullptr;
    }
}

cv::Mat FfmpegAdapter::toMat(AVFrame* frame) {
    cv::Mat img(frame->height, frame->width, CV_8UC3);
    for (int y = 0; y < frame->height; ++y) {
        std::memcpy(img.data + y * img.step, frame->data[0] + y * frame->linesize[0], frame->width * 3);
    }
    return img;
}

void FfmpegAdapter::fromMat(const cv::Mat& img, AVFrame* frame) {
    for (int y = 0; y < img.rows; ++y) {
        std::memcpy(frame->data[0] + y * frame->linesize[0], img.data + y * img.step, img.cols * 3);
    }
}

} // namespace adapters
