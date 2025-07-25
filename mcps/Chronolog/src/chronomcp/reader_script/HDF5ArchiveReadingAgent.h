#ifndef CHRONOLOG_HDF5ARCHIVEREADINGAGENT_H
#define CHRONOLOG_HDF5ARCHIVEREADINGAGENT_H

#include <list>
#include <string>
#include <map>
#include <filesystem>
#include <thallium.hpp>
#include <utility>

#include "StoryChunkIngestionQueue.h"

namespace tl = thallium;

namespace chronolog
{

class HDF5ArchiveReadingAgent
{
public:
    explicit HDF5ArchiveReadingAgent(std::string const &archive_path)
        : archive_path_(archive_path)
    {}

    ~HDF5ArchiveReadingAgent() = default;

    int initialize()
    {
        LOG_INFO("[HDF5ArchiveReadingAgent] Initializing,scanning archive path {} to create the map ...",
                 archive_path_);
        createStartTimeFileNameMap();
        return setUpFsMonitoring();
    }

    int shutdown()
    {
        archive_dir_monitoring_stream_->join();
        archive_dir_monitoring_thread_->join();
        return 0;
    }

    int readArchivedStory(const ChronicleName&, const StoryName&, uint64_t, uint64_t, std::list<StoryChunk*>&);

    static std::string getChronicleName(const std::string &file_name)
    {
        // Example file name: /home/kfeng/chronolog/Debug/output/chronicle_0_0.story_0_0.1736806500.vlen.h5
        std::string base_name = file_name.substr(file_name.find_last_of("/\\") + 1);
        std::string chronicle_name = base_name.substr(0, base_name.find_first_of('.'));
        return chronicle_name;
    }

    static std::string getStoryName(const std::string &file_name)
    {
        // Example file name: /home/kfeng/chronolog/Debug/output/chronicle_0_0.story_0_0.1736806500.vlen.h5
        std::string base_name = file_name.substr(file_name.find_last_of("/\\") + 1);
        size_t first_dot = base_name.find_first_of('.');
        size_t second_dot = base_name.find_first_of('.', first_dot + 1);
        std::string story_name = base_name.substr(first_dot + 1, second_dot - first_dot - 1);
        return story_name;
    }

    static uint64_t getStartTime(const std::string &file_name)
    {
        // Example file name: /home/kfeng/chronolog/Debug/output/chronicle_0_0.story_0_0.1736806500.vlen.h5
        std::string base_name = file_name.substr(file_name.find_last_of("/\\") + 1);
        size_t first_dot = base_name.find_first_of('.');
        size_t second_dot = base_name.find_first_of('.', first_dot + 1);
        size_t third_dot = base_name.find_first_of('.', second_dot + 1);
        std::string start_time_str = base_name.substr(second_dot + 1, third_dot - second_dot - 1);
        return std::stoull(start_time_str);
    }

private:
    int setUpFsMonitoring();

    int fsMonitoringThreadFunc();

    int createStartTimeFileNameMap()
    {
        // iterate over the HDF5 files in the archive directory to get the list of files
        // update the start_time_file_name_map_ with the start time and file name
        std::lock_guard<std::mutex> lock(start_time_file_name_map_mutex_);
        for(const auto &entry : std::filesystem::directory_iterator(archive_path_)) {
            std::string chronicle_name = getChronicleName(entry.path().string());
            std::string story_name = getStoryName(entry.path().string());
            uint64_t start_time = getStartTime(entry.path().string());
            start_time_file_name_map_[std::make_tuple(chronicle_name, story_name, start_time)] = entry.path().string();
        }
        LOG_DEBUG("[HDF5ArchiveReadingAgent] Created start_time_file_name_map_ with {} entries.",
                  start_time_file_name_map_.size());
        return 0;
    }

    int addFileToStartTimeFileNameMap(const std::string &file_name)
    {
        std::lock_guard<std::mutex> lock(start_time_file_name_map_mutex_);
        std::string chronicle_name = getChronicleName(file_name);
        std::string story_name = getStoryName(file_name);
        uint64_t start_time = getStartTime(file_name);
        start_time_file_name_map_[std::make_tuple(chronicle_name, story_name, start_time)] = file_name;
        LOG_DEBUG("[HDF5ArchiveReadingAgent] Added file {} to start_time_file_name_map_.", file_name);
        LOG_DEBUG("[HDF5ArchiveReadingAgent] start_time_file_name_map_ has {} entries.",
                  start_time_file_name_map_.size());
        return 0;
    }

    int removeFileFromStartTimeFileNameMap(const std::string &file_name)
    {
        std::lock_guard<std::mutex> lock(start_time_file_name_map_mutex_);
        std::string chronicle_name = getChronicleName(file_name);
        std::string story_name = getStoryName(file_name);
        uint64_t start_time = getStartTime(file_name);
        start_time_file_name_map_.erase(std::make_tuple(chronicle_name, story_name, start_time));
        LOG_DEBUG("[HDF5ArchiveReadingAgent] Removed file {} from start_time_file_name_map_.", file_name);
        LOG_DEBUG("[HDF5ArchiveReadingAgent] start_time_file_name_map_ has {} entries.",
                  start_time_file_name_map_.size());
        return 0;
    }

    int renameFileInStartTimeFileNameMap(const std::string &old_file_name, const std::string &new_file_name)
    {
        removeFileFromStartTimeFileNameMap(old_file_name);
        addFileToStartTimeFileNameMap(new_file_name);
        LOG_DEBUG("[HDF5ArchiveReadingAgent] Renamed file {} to {} in start_time_file_name_map_.",
                  old_file_name, new_file_name);
        LOG_DEBUG("[HDF5ArchiveReadingAgent] start_time_file_name_map_ has {} entries.",
                  start_time_file_name_map_.size());
        return 0;
    }

    std::string archive_path_;
    std::map<std::tuple<std::string, std::string, uint64_t>, std::string> start_time_file_name_map_;
    std::mutex start_time_file_name_map_mutex_;
    tl::managed <tl::xstream> archive_dir_monitoring_stream_;
    tl::managed <tl::thread> archive_dir_monitoring_thread_;
};

} // chronolog

#endif //CHRONOLOG_HDF5ARCHIVEREADINGAGENT_H
