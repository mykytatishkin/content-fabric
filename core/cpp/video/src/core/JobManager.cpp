#include "JobManager.hpp"
#include "VideoPipelineEngine.hpp"
#include "../adapters/ConfigLoader.hpp"
#include "../operations/SubtitleTranslateOperation.hpp"
#include "../operations/SubtitleRemoveOperation.hpp"
#include "../operations/WatermarkRemoveOperation.hpp"
#include "../operations/VoiceoverReplaceOperation.hpp"
#include "../utils/Logging.hpp"

#include <filesystem>

namespace core {

JobManager::JobManager(cli::ProgramOptions options) : options_(std::move(options)) {
    loadConfig();
}

void JobManager::loadConfig() {
    if (options_.configPath) {
        config_ = adapters::ConfigLoader::loadJson(*options_.configPath);
    }
}

VideoJob JobManager::buildJobFromCli() {
    std::vector<OperationDescriptor> ops;
    for (const auto& op : options_.operations) {
        nlohmann::json params;
        if (op == "subtitles_translate") {
            params["src_lang"] = options_.subtitleSrcLang.value_or("auto");
            params["dst_lang"] = options_.subtitleDstLang.value_or("auto");
        } else if (op == "voiceover") {
            params["lang"] = options_.ttsLang.value_or("auto");
            params["base_url"] = options_.ttsBaseUrl.value_or("");
            params["api_key"] = options_.ttsApiKey.value_or("");
        }
        ops.push_back(OperationDescriptor{op, params});
    }
    return VideoJob(options_.input, options_.output, ops);
}

VideoJob JobManager::buildJobFromConfig(const nlohmann::json& jobCfg) {
    std::vector<OperationDescriptor> ops;
    if (jobCfg.contains("operations")) {
        for (const auto& op : jobCfg.at("operations")) {
            OperationDescriptor desc;
            desc.type = op.at("type").get<std::string>();
            desc.params = op;
            ops.push_back(desc);
        }
    }
    std::string input = jobCfg.value("input", options_.input);
    std::string output = jobCfg.value("output", options_.output);
    return VideoJob(input, output, ops);
}

std::vector<VideoJob> JobManager::buildJobs() {
    if (options_.configPath && config_.is_object()) {
        if (config_.contains("jobs")) {
            std::vector<VideoJob> jobs;
            for (const auto& jobCfg : config_.at("jobs")) {
                jobs.push_back(buildJobFromConfig(jobCfg));
            }
            return jobs;
        }
        return {buildJobFromConfig(config_)};
    }
    return {buildJobFromCli()};
}

void JobManager::run(const std::vector<VideoJob>& jobs) {
    for (const auto& job : jobs) {
        LOG_INFO("Processing job: {} -> {}", job.input(), job.output());
        core::VideoPipelineEngine engine(job);
        engine.run();
    }
}

} // namespace core
