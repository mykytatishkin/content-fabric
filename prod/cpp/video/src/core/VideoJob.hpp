#pragma once

#include <string>
#include <vector>
#include <memory>
#include <nlohmann/json.hpp>

namespace operations {
class IVideoOperation;
}

namespace core {

struct OperationDescriptor {
    std::string type;
    nlohmann::json params;
};

class VideoJob {
public:
    VideoJob() = default;
    VideoJob(std::string inputPath, std::string outputPath, std::vector<OperationDescriptor> ops);

    const std::string& input() const { return inputPath_; }
    const std::string& output() const { return outputPath_; }
    const std::vector<OperationDescriptor>& operations() const { return operations_; }

private:
    std::string inputPath_;
    std::string outputPath_;
    std::vector<OperationDescriptor> operations_;
};

} // namespace core
