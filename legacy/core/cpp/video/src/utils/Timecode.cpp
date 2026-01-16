#include "Timecode.hpp"
#include <sstream>
#include <iomanip>

namespace utils {

std::string Timecode::toString(int64_t ms) {
    int64_t totalSeconds = ms / 1000;
    int hours = static_cast<int>(totalSeconds / 3600);
    int minutes = static_cast<int>((totalSeconds % 3600) / 60);
    int seconds = static_cast<int>(totalSeconds % 60);
    int milliseconds = static_cast<int>(ms % 1000);

    std::ostringstream oss;
    oss << std::setw(2) << std::setfill('0') << hours << ":"
        << std::setw(2) << std::setfill('0') << minutes << ":"
        << std::setw(2) << std::setfill('0') << seconds << ","
        << std::setw(3) << std::setfill('0') << milliseconds;
    return oss.str();
}

} // namespace utils
