#pragma once

#include <string>
#include <vector>
#include <optional>
#include <nlohmann/json.hpp>

namespace cli {

struct ProgramOptions {
    std::vector<std::string> operations;
    std::string input;
    std::string output;
    std::optional<std::string> configPath;
    std::optional<std::string> subtitleSrcLang;
    std::optional<std::string> subtitleDstLang;
    std::optional<std::string> ttsLang;
    std::optional<std::string> ttsBaseUrl;
    std::optional<std::string> ttsApiKey;
};

class ArgsParser {
public:
    ProgramOptions parse(int argc, char** argv);
};

} // namespace cli
