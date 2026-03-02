#pragma once

#include <vector>
#include <string>
#include <nlohmann/json.hpp>
#include "cli/ArgsParser.hpp"
#include "VideoJob.hpp"

namespace core {

class JobManager {
public:
    explicit JobManager(cli::ProgramOptions options);
    std::vector<VideoJob> buildJobs();
    void run(const std::vector<VideoJob>& jobs);

private:
    cli::ProgramOptions options_;
    nlohmann::json config_;
    void loadConfig();
    VideoJob buildJobFromConfig(const nlohmann::json& jobCfg);
    VideoJob buildJobFromCli();
};

} // namespace core
