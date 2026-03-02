#include "ArgsParser.hpp"

#include <CLI/CLI.hpp>
#include <filesystem>
#include <sstream>

namespace cli {

ProgramOptions ArgsParser::parse(int argc, char** argv) {
    CLI::App app{"video_tool - configurable video processing pipeline"};

    ProgramOptions opts;
    std::string operationsStr;

    app.add_option("--input", opts.input, "Input file or directory")->required();
    app.add_option("--output", opts.output, "Output file or directory")->required();
    app.add_option("--type", operationsStr, "Comma-separated operations (subtitles_translate, subtitles_remove, watermark_remove, voiceover)");
    app.add_option("--config", opts.configPath, "Path to job config JSON");
    app.add_option("--subtitle-lang-src", opts.subtitleSrcLang, "Subtitle source language");
    app.add_option("--subtitle-lang-dst", opts.subtitleDstLang, "Subtitle destination language");
    app.add_option("--tts-lang", opts.ttsLang, "TTS language for voiceover");
    app.add_option("--tts-base-url", opts.ttsBaseUrl, "TTS service base URL");
    app.add_option("--tts-api-key", opts.ttsApiKey, "TTS service API key");

    app.allow_extras();
    app.parse(argc, argv);

    if (!operationsStr.empty()) {
        std::stringstream ss(operationsStr);
        std::string item;
        while (std::getline(ss, item, ',')) {
            if (!item.empty()) {
                opts.operations.push_back(item);
            }
        }
    }

    return opts;
}

} // namespace cli
