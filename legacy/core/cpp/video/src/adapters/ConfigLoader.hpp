#pragma once

#include <nlohmann/json.hpp>
#include <string>

namespace adapters {

class ConfigLoader {
public:
    static nlohmann::json loadJson(const std::string& path);
};

} // namespace adapters
