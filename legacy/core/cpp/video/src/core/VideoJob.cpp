#include "VideoJob.hpp"

namespace core {

VideoJob::VideoJob(std::string inputPath, std::string outputPath, std::vector<OperationDescriptor> ops)
    : inputPath_(std::move(inputPath)), outputPath_(std::move(outputPath)), operations_(std::move(ops)) {}

} // namespace core
