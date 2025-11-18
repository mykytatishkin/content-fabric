#include "ConfigLoader.hpp"

#include <fstream>
#include <stdexcept>

namespace adapters {

nlohmann::json ConfigLoader::loadJson(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) {
        throw std::runtime_error("Cannot open config: " + path);
    }
    nlohmann::json j;
    ifs >> j;
    return j;
}

} // namespace adapters
