#include "cli/ArgsParser.hpp"
#include "core/JobManager.hpp"
#include "utils/Logging.hpp"

int main(int argc, char** argv) {
    try {
        cli::ArgsParser parser;
        auto options = parser.parse(argc, argv);

        core::JobManager manager(options);
        auto jobs = manager.buildJobs();
        manager.run(jobs);
    } catch (const std::exception& ex) {
        LOG_ERROR("Fatal error: {}", ex.what());
        return 1;
    }
    return 0;
}
