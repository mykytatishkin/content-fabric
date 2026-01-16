#pragma once

#include <vector>
#include <string>
#include <optional>
#include <memory>
#include <cstdint>
#include <nlohmann/json.hpp>

extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/avutil.h>
}

namespace core {

struct SubtitleCue {
    int64_t start_ms{};
    int64_t end_ms{};
    std::string text;
};

struct SubtitleTrack {
    std::vector<SubtitleCue> cues;
    std::string language;
};

struct AudioData {
    std::vector<uint8_t> bytes;
    int sampleRate{48000};
    int channels{2};
    AVSampleFormat format{AV_SAMPLE_FMT_S16};
};

struct VideoContext {
    AVFormatContext* inputFormat{nullptr};
    AVCodecContext* videoDecoder{nullptr};
    AVCodecContext* videoEncoder{nullptr};
    AVFormatContext* outputFormat{nullptr};
    int videoStreamIndex{-1};
    int audioStreamIndex{-1};
    int subtitleStreamIndex{-1};

    SubtitleTrack subtitles;
    AudioData generatedVoiceover;
};

} // namespace core
