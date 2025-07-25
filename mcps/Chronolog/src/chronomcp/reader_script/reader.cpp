#include <csignal>
#include <iostream>
#include <string>
#include <list>
#include <climits>

#include "HDF5ArchiveReadingAgent.h"
#include "ConfigurationManager.h"
#include "chrono_monitor.h"

namespace tl = thallium;

std::atomic<bool> running(true);
std::list<chronolog::StoryChunk*> list_of_chunks;
chronolog::HDF5ArchiveReadingAgent* agent_ptr = nullptr;

void signalHandler(int sig) {
    std::cout << "Interrupt (" << sig << ")\n";
    for(auto *c : list_of_chunks) delete c;
    if(agent_ptr) agent_ptr->shutdown(), delete agent_ptr;
    std::exit(sig);
}

int main(int argc, char** argv) {
    // ── defaults ──
    std::string conf_file;
    std::string chronicle_name = "LLM";
    std::string story_name     = "conversation";
    uint64_t start_time = 1736800000000000000ULL;
    uint64_t end_time   = 1745539189396295796ULL + 1000000000000000ULL;

    // ── simple flag loop ──
    for(int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if((a == "-c" || a == "--config") && i+1 < argc) {
            conf_file = argv[++i];
        } else if(a == "-C" && i+1 < argc) {
            chronicle_name = argv[++i];
        } else if(a == "-S" && i+1 < argc) {
            story_name = argv[++i];
        } else if((a == "-st" || a == "--start") && i+1 < argc) {
            start_time = std::stoull(argv[++i]);
        } else if((a == "-et" || a == "--end") && i+1 < argc) {
            end_time = std::stoull(argv[++i]);
        }
        // else: ignore unknowns
    }
    if(conf_file.empty()) {
        std::cerr << "Usage: " << argv[0]
                  << " -c <config.json>"
                  << " [-C chronicle] [-S story]"
                  << " [-s startTime] [-e endTime]\n";
        return EXIT_FAILURE;
    }

    // ── initialize logger ──
    ChronoLog::ConfigurationManager conf(conf_file);
    int r = chronolog::chrono_monitor::initialize(
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGTYPE,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGFILE,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGLEVEL,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGNAME,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGFILESIZE,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.LOGFILENUM,
        conf.CLIENT_CONF.CLIENT_LOG_CONF.FLUSHLEVEL
    );
    if(r == 1) return EXIT_FAILURE;

    signal(SIGINT, signalHandler);
    tl::abt scope;

    // ── read & print ──
    std::string archive_path = conf.GRAPHER_CONF.EXTRACTOR_CONF.story_files_dir;
    agent_ptr = new chronolog::HDF5ArchiveReadingAgent(archive_path);
    agent_ptr->initialize();

    std::cout << "Reading [" << start_time << "," << end_time << "] from "
              << chronicle_name << "." << story_name << "\n";

    agent_ptr->readArchivedStory(
        chronicle_name, story_name, start_time, end_time, list_of_chunks
    );

    std::cout << list_of_chunks.size() << " chunk(s) returned.\n";
    for(auto *chunk : list_of_chunks) {
        std::cout << "Chunk with " << chunk->getEventCount() << " events:\n";
        for(auto const &kv : *chunk) {
            auto const &e = kv.second;
            std::cout
                << "  storyId="   << e.storyId
                << ", time="     << e.eventTime
                << ", clientId=" << e.clientId
                << ", index="    << e.eventIndex
                << ", record=\"" << e.logRecord << "\"\n";
        }
        delete chunk;
    }

    // clean up story-chunks
    for(auto *chunk : list_of_chunks) {
        delete chunk;
    }
    list_of_chunks.clear();

    // shut down the archive-reader threads and delete
    agent_ptr->shutdown();                // joins the monitoring thread :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}
    delete agent_ptr;
    agent_ptr = nullptr;

    return 0;

}

