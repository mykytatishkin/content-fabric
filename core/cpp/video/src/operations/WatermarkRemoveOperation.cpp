#include "WatermarkRemoveOperation.hpp"
#include "../adapters/FfmpegAdapter.hpp"
#include "../utils/Logging.hpp"

#include <opencv2/imgproc.hpp>
#include <opencv2/photo.hpp>

namespace operations {

WatermarkRemoveOperation::WatermarkRemoveOperation(const nlohmann::json& params) {
    if (params.contains("regions")) {
        for (const auto& r : params.at("regions")) {
            WatermarkRegion region;
            region.x = r.value("x", 0);
            region.y = r.value("y", 0);
            region.width = r.value("width", 0);
            region.height = r.value("height", 0);
            region.method = r.value("method", std::string("blur"));
            regions_.push_back(region);
        }
    }
}

void WatermarkRemoveOperation::prepare(core::VideoContext&) {}

void WatermarkRemoveOperation::apply(cv::Mat& img) {
    for (const auto& r : regions_) {
        cv::Rect rect(r.x, r.y, r.width, r.height);
        rect = rect & cv::Rect(0, 0, img.cols, img.rows);
        if (rect.area() <= 0) continue;
        if (r.method == "inpaint") {
            cv::Mat mask = cv::Mat::zeros(img.size(), CV_8UC1);
            cv::rectangle(mask, rect, cv::Scalar(255), cv::FILLED);
            cv::inpaint(img, mask, img, 3, cv::INPAINT_TELEA);
        } else {
            cv::Mat roi = img(rect);
            cv::GaussianBlur(roi, roi, cv::Size(11, 11), 0);
        }
    }
}

void WatermarkRemoveOperation::processFrame(core::VideoContext& ctx, AVFrame* frame, int64_t) {
    if (regions_.empty()) return;
    cv::Mat img = adapters::FfmpegAdapter::toMat(frame);
    apply(img);
    adapters::FfmpegAdapter::fromMat(img, frame);
}

void WatermarkRemoveOperation::finalize(core::VideoContext&) {}

} // namespace operations
