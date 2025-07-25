# Installation Guide for ADIOS2

Below are two installation method: building from source (with full MPI and optional dependencies), and a quick **non‑MPI** install via `pip`.

## 1. Build and Install from Source (with MPI)

### Prerequisites

* **Compiler & Build Tools**

  * CMake ≥ 3.6
  * A C++11‑capable compiler (GCC ≥ 4.8.1, Intel ≥ 15, PGI ≥ 15, or Clang)
  * `make`, `git`
* **MPI library**

  * OpenMPI, MPICH, or equivalent (must match C++ compiler)
* **Optional dependencies** (enable via CMake flags below)

  * HDF5 (`libhdf5-dev` / `hdf5-devel`)
  * Python 3 + development headers (`python3-dev` / `python3-devel`)
  * NumPy & mpi4py (`pip install numpy mpi4py`)
  * Fortran compiler (if using Fortran bindings)
  * Compression libs: BZip2, ZFP, SZ, Blosc2, etc.

### Step‑by‑Step

1. **Clone the ADIOS2 repo**

   ```bash
   git clone https://github.com/ornladios/ADIOS2.git
   cd ADIOS2
   ```
2. **Install system packages** (Ubuntu example)

   ```bash
   sudo apt-get update
   sudo apt-get install -y \
     build-essential cmake git \
     libhdf5-dev hdf5-tools \
     openmpi-bin libopenmpi-dev \
     python3 python3-dev python3-pip \
     libbz2-dev zlib1g-dev libzstd-dev libblosc-dev
   ```
3. **Create a build directory**

   ```bash
   mkdir build && cd build
   ```
4. **Configure with CMake**

   ```bash
    cmake ../ADIOS2 \
    -DADIOS2_BUILD_EXAMPLES=ON \
    -DADIOS2_USE_Python=ON \
    -DCMAKE_PREFIX_PATH="/usr/bin" \
    -DCMAKE_INSTALL_PREFIX=/$HOME/adios
   ```

5. **Install**

   ```bash
   sudo make install
   ```
6. **Set up your environment** (add to `~/.bashrc` or similar)

   ```bash
   export LD_LIBRARY_PATH=/adios2/lib:$LD_LIBRARY_PATH
   export PYTHONPATH=/adios2/local/lib/python3.12/site-packages:$PYTHONPATH
   ```

## 2. Quick Non‑MPI Install via pip

> **Note:** this route builds only the serial (no‑MPI) Python bindings. Use the source build above if you need MPI‑enabled C++ or Python support.

1. **Create & activate a virtual environment**

   ```bash
   python3 -m venv adios2-venv
   source adios2-venv/bin/activate
   ```
2. **Install ADIOS2 and Python dependencies**

   ```bash
   pip install --upgrade pip
   pip install adios2 numpy mpi4py
   ```
