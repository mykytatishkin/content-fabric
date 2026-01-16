#pragma once

#include <cstdint>
#include <string>

namespace utils {

class Timecode {
public:
    static std::string toString(int64_t ms);
};

} // namespace utils
