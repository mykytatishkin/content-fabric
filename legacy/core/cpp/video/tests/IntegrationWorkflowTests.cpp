#include "adapters/ConfigLoader.hpp"
#include "core/VideoJob.hpp"
#include "utils/Timecode.hpp"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>

int main() {
    const auto json = adapters::ConfigLoader::loadJson("configs/examples/job_example.json");

    // Build a job similar to runtime behavior
    std::vector<core::OperationDescriptor> ops;
    if (!json.contains("operations")) {
        std::cerr << "Missing operations array in config\n";
        return EXIT_FAILURE;
    }

    for (const auto& op : json.at("operations")) {
        if (!op.contains("type")) {
            std::cerr << "Operation missing type\n";
            return EXIT_FAILURE;
        }
        core::OperationDescriptor desc;
        desc.type = op.at("type").get<std::string>();
        desc.params = op;
        ops.push_back(desc);
    }

    const std::string input = json.contains("input") ? json.at("input").get<std::string>() : std::string{};
    const std::string output = json.contains("output") ? json.at("output").get<std::string>() : std::string{};

    core::VideoJob job(input, output, ops);

    if (job.input() != "videos/demo.mp4" || job.output() != "output/demo_uk.mp4") {
        std::cerr << "Unexpected job paths\n";
        return EXIT_FAILURE;
    }

    if (job.operations().size() != 3) {
        std::cerr << "Unexpected operation count\n";
        return EXIT_FAILURE;
    }

    const auto& translate = job.operations().front();
    const auto translateDst = translate.params.contains("dst_lang")
        ? translate.params.at("dst_lang").get<std::string>()
        : std::string{};
    if (translate.type != "subtitles_translate" || translateDst != "uk") {
        std::cerr << "Translate operation not preserved\n";
        return EXIT_FAILURE;
    }

    bool foundWatermarkRegion = false;
    for (const auto& op : job.operations()) {
        if (op.type == "watermark_remove" && op.params.contains("regions")) {
            auto regions = op.params.at("regions");
            if (regions.is_array() && regions.size() > 0) {
                nlohmann::json region = regions[0];
                foundWatermarkRegion = region.value("width", 0) == 200 && region.value("method", "") == "inpaint";
            }
        }
    }

    if (!foundWatermarkRegion) {
        std::cerr << "Watermark configuration not propagated\n";
        return EXIT_FAILURE;
    }

    // Build a synthetic TTS request payload to ensure combined use of config data and timecodes
    nlohmann::json ttsPayload;
    auto voiceIt = std::find_if(job.operations().begin(), job.operations().end(), [](const auto& op) {
        return op.type == "voiceover";
    });
    if (voiceIt == job.operations().end()) {
        std::cerr << "Voiceover operation missing\n";
        return EXIT_FAILURE;
    }

    const std::string voiceLang = voiceIt->params.contains("lang") ? voiceIt->params.at("lang").get<std::string>() : std::string{};
    ttsPayload["language"] = voiceLang;
    nlohmann::json::array_t subtitlesArray;
    subtitlesArray.push_back(nlohmann::json{{"start", utils::Timecode::toString(0)},
                                            {"end", utils::Timecode::toString(2'200)},
                                            {"text", "Hello world"}});
    ttsPayload["subtitles"] = nlohmann::json(subtitlesArray);

    if (ttsPayload["language"].get<std::string>() != "uk") {
        std::cerr << "Voiceover language mismatch\n";
        return EXIT_FAILURE;
    }

    const auto firstCueEnd = ttsPayload["subtitles"][0].value("end", std::string{});
    if (firstCueEnd != "00:00:02,200") {
        std::cerr << "Unexpected cue timecode" << firstCueEnd << "\n";
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
