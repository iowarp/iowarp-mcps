cmake_minimum_required(VERSION 3.25)
project(HDF5SingleFileReader)

# Where your ChronoLog checkout is:
set(CHRONOLOG_ROOT        "$ENV{HOME}/ChronoLog"
    CACHE PATH "Root of ChronoLog repo")
set(CHRONOLOG_PLAYER_ROOT "${CHRONOLOG_ROOT}/ChronoPlayer"
    CACHE PATH "ChronoPlayer subfolder")

find_package(Thallium REQUIRED)
find_package(spdlog  REQUIRED)
find_package(HDF5    REQUIRED COMPONENTS C CXX)

# ─── Tell CMake where libchronolog_client lives ───
# (adjust this if your build directory is elsewhere)
link_directories(/home/ssonar/chronolog/Debug/lib)

# sanity check
if(NOT EXISTS "/home/ssonar/chronolog/Debug/lib/libchronolog_client.so")
  message(FATAL_ERROR
    "Cannot find libchronolog_client.so under ${CHRONOLOG_ROOT}/build/lib{,64}/\n"
    "Please adjust the paths in link_directories().")
endif()

include_directories(
  ${CHRONOLOG_ROOT}/chrono_common
  ${CHRONOLOG_ROOT}/ChronoAPI/ChronoLog/include
  ${CHRONOLOG_PLAYER_ROOT}/include
)

add_executable(hdf5_file_reader
  reader.cpp
  ${CHRONOLOG_PLAYER_ROOT}/HDF5ArchiveReadingAgent.cpp
  ${CHRONOLOG_ROOT}/chrono_common/StoryChunk.cpp
)

target_link_libraries(hdf5_file_reader
  chronolog_client   # now found under the directories above
  thallium
  ${HDF5_LIBRARIES}
)

set_target_properties(hdf5_file_reader
  PROPERTIES INSTALL_RPATH_USE_LINK_PATH TRUE
)

