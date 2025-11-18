cmake_minimum_required(VERSION 3.15)
project(video_tool LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(VIDEO_TOOL_ENABLE_LOGGING "Enable spdlog logging" ON)
option(VIDEO_TOOL_BUILD_TOOLS "Build the main video_tool binary and core library" ON)
option(VIDEO_TOOL_BUILD_TESTS "Build integration tests" ON)

find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
    add_library(nlohmann_json INTERFACE)
    target_include_directories(nlohmann_json INTERFACE ${PROJECT_SOURCE_DIR}/third_party)
    add_library(nlohmann_json::nlohmann_json ALIAS nlohmann_json)
endif()

if(VIDEO_TOOL_BUILD_TOOLS)
    find_package(PkgConfig REQUIRED)
    find_package(FFmpeg COMPONENTS AVCODEC AVFORMAT AVFILTER AVUTIL SWSCALE REQUIRED)
    find_package(OpenCV REQUIRED)
    find_package(CLI11 REQUIRED)
    find_package(CURL REQUIRED)

    if(VIDEO_TOOL_ENABLE_LOGGING)
        find_package(spdlog QUIET)
    endif()

    add_library(video_tool_lib
        src/cli/ArgsParser.cpp
        src/core/VideoJob.cpp
        src/core/JobManager.cpp
        src/core/VideoPipelineEngine.cpp
        src/operations/SubtitleTranslateOperation.cpp
        src/operations/SubtitleRemoveOperation.cpp
        src/operations/WatermarkRemoveOperation.cpp
        src/operations/VoiceoverReplaceOperation.cpp
        src/adapters/FfmpegAdapter.cpp
        src/adapters/SubtitleAdapter.cpp
        src/adapters/AudioAdapter.cpp
        src/adapters/TtsClient.cpp
        src/adapters/ConfigLoader.cpp
        src/utils/Timecode.cpp
    )

    add_executable(video_tool src/main.cpp)

    target_include_directories(video_tool_lib PUBLIC ${PROJECT_SOURCE_DIR}/src)

    set(FFMPEG_LIBS ${FFMPEG_LIBRARIES})

    if (TARGET spdlog::spdlog)
        set(LOGGING_LIB spdlog::spdlog)
    endif()

    if(NOT LOGGING_LIB)
        add_library(logging_stub INTERFACE)
        target_include_directories(logging_stub INTERFACE ${PROJECT_SOURCE_DIR}/src)
        set(LOGGING_LIB logging_stub)
    endif()

    target_link_libraries(video_tool_lib
        PUBLIC
            CLI11::CLI11
            nlohmann_json::nlohmann_json
            CURL::libcurl
            ${OpenCV_LIBS}
            ${FFMPEG_LIBS}
            ${LOGGING_LIB}
    )

    target_link_libraries(video_tool PRIVATE video_tool_lib)

    target_compile_definitions(video_tool PRIVATE $<$<BOOL:${VIDEO_TOOL_ENABLE_LOGGING}>:VIDEO_TOOL_ENABLE_LOGGING>)
    target_compile_definitions(video_tool_lib PRIVATE $<$<BOOL:${VIDEO_TOOL_ENABLE_LOGGING}>:VIDEO_TOOL_ENABLE_LOGGING>)

    install(TARGETS video_tool RUNTIME DESTINATION bin)
    install(DIRECTORY configs/ DESTINATION share/video_tool/configs)
    install(FILES README.md DESTINATION share/video_tool)
endif()

if(VIDEO_TOOL_BUILD_TESTS)
    enable_testing()

    add_executable(integration_workflow_tests
        tests/IntegrationWorkflowTests.cpp
        src/adapters/ConfigLoader.cpp
        src/utils/Timecode.cpp
        src/core/VideoJob.cpp
    )

    target_include_directories(integration_workflow_tests PRIVATE ${PROJECT_SOURCE_DIR}/src)
    target_link_libraries(integration_workflow_tests PRIVATE nlohmann_json::nlohmann_json)

    add_test(NAME IntegrationWorkflowTests COMMAND integration_workflow_tests WORKING_DIRECTORY ${PROJECT_SOURCE_DIR})
endif()
