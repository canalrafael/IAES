# IAES: Intelligent (I) Run-Time Monitoring and Actuation Architecture (A) for Embedded (E) Systems (S)

IAES is a research project designed to bridge the gap between **Real-Time Systems (RTS)** and **Microarchitectural Security**. It provides a lightweight, AI-driven monitoring architecture to detect microarchitectural attacks and cross-core interference in **Mixed-Criticality Systems (MCS)**.

This project is implemented on the **Raspberry Pi 4 (BCM2711)** using the **Bao Hypervisor** to enforce spatial and temporal isolation between a Linux "best-effort" domain and a FreeRTOS "safety-critical" domain.

## 🔬 Research Context
Modern Multi-Processor Systems-on-Chip (MPSoC) share critical hardware resources (Last-Level Cache, System Bus, Branch Predictors). While efficient, these shared resources are vulnerable to:
- **MicroarchitecturalAttacks** (e.g., Spectre, Meltdown).
- **Resource Contention/DoS** (e.g., Cache eviction, Memory bandwidth saturation).

IAES addresses these by using **Hardware Performance Counters (HPCs)** as security sensors and **TinyML** models to classify system behavior in real-time without the need for dedicated AI accelerators.

## 🚀 Key Contributions
1. **Embedded Microarchitectural Dataset**: A reproducible dataset capturing *Normal* vs. *Interference* execution patterns.
2. **Attack Porting**: Implementations of representative microarchitectural attacks ported to ARMv8.
3. **Lightweight AI Detector**: A computationally efficient Multi-Layer Perceptron (MLP) using sliding temporal windows for deterministic anomaly detection.
4. **Bao-based Architecture**: Integration with the Bao Hypervisor for run-time monitoring on COTS (Commercial Off-The-Shelf) platforms.

## 📝 Scientific Publication
This repository and the experimental data provided are part of the research submitted to the **31st IEEE International Conference on Emerging Technologies and Factory Automation (ETFA 2026)**.

## 🛠 Project Structure
- `/platforms/rpi4`: Configuration files and device trees for the Raspberry Pi 4.
- `/demos`: Source code for the Mixed-Criticality demos (Linux + FreeRTOS).
- `/scripts`: Automation for building and deploying the hypervisor image.
- `.gitignore`: Configured to exclude heavy build artifacts (`wrkdir/`) and binaries.

## 🏗 Build Instructions

The project uses a **Dockerized build environment** for full portability. All cross-compilation toolchains and dependencies are encapsulated in a Docker image, so no manual toolchain setup is required.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running.
- An SD card mounted at `/media/$USER/BOOT/` (for deployment).
- Internet access on first run: `./build.sh` fetches the Raspberry Pi
  firmware and builds u-boot and TF-A's `bl31.bin` automatically (cached
  afterwards in `bao-demos/wrkdir/imgs/rpi4/`).

### Quick Start

```bash
# 1. Initialize submodules (Bao Hypervisor Core)
git submodule update --init --recursive

# 2. Full build + fetch boot assets + copy to SD card (one command)
./build.sh
```

### Available Build Commands

| Command | Description |
|---|---|
| `./build.sh` | Full build (all VMs + Bao), fetch boot assets and copy everything to SD card |
| `./build.sh vms` | Build all VMs (vm_0 through vm_3) |
| `./build.sh vm <N>` | Build a specific VM (0–3). VM 3 (Linux) is slow on first build |
| `./build.sh bao` | Build only the Bao hypervisor |
| `./build.sh assets` | Fetch/build the Raspberry Pi firmware, u-boot and `bl31.bin` |
| `./build.sh copy` | Copy boot files to SD card (skip build) |
| `./build.sh clean` | Clean all build artifacts |
| `./build.sh shell` | Open an interactive shell inside the build container |

### Build Output
The final binary is generated at:
```
bao-demos/wrkdir/imgs/rpi4/linux+freertos/bao.bin
```

### Custom SD Card Path
If your SD card is mounted at a non-default location, use the `BAO_DEMOS_SDCARD` environment variable:
```bash
BAO_DEMOS_SDCARD=/path/to/mount ./build.sh copy
```

---

## ⚙️ Changing the Execution Scenario

The system supports **8 pre-defined data collection scenarios** that control which VMs are active and what workloads they execute. The scenario is configured in a single header file:

```
bao-demos/wrkdir/srcs/guest_common/inc/regulation.h
```

### How to Change the Scenario

Open `regulation.h` and locate the following line (around line 109):

```c
#define SCENARIO 7 // <-- CHANGE HERE TO SWITCH SCENARIO
```

Change the number to one of the scenarios described below, then **rebuild the project**:

```bash
./build.sh
```

### Available Scenarios

| Scenario | VMs Active | Workload Description | Labels |
|:---:|---|---|---|
| **1** | VM0 + VM1 | Benchmarks only on 1 core (sequential) | bench=0 |
| **2** | VM0 + VM3 | Attacks only on 1 core | attack=1 |
| **3** | VM0 + VM1 + VM3 | Benchmarks + Attacks on 2 cores | bench=2, attack=3 |
| **4** | VM0 + VM1 + VM2 | Benchmarks on 2 cores (sequential) | bench=0 |
| **5** | VM0 + VM1 + VM2 | Benchmarks on 2 cores (**random**) | bench=0 |
| **6** | VM0 + VM1 + VM2 + VM3 | Random benchmarks (VM1+VM2) + Attacks (VM3) | bench=2, attack=3 |
| **7** | VM0 + VM1 + VM2 + VM3 | Random benchmarks + Attacks **interleaved with benchmarks** (VM3 cycle: bench → Spectre → bench → Armageddon → bench → Meltdown → repeat) | bench=2, attack=3 |
| **8** | VM0 + VM1 + VM2 + VM3 | Fixed benchmarks (VM1=SHA, VM2=FFT) + persistent Meltdown (VM3) | bench=2, attack=3 |

### VM Roles

| VM | Role |
|---|---|
| **VM0** | PMU Monitor — always active, collects hardware performance counter data |
| **VM1** | FreeRTOS benchmark core 1 |
| **VM2** | FreeRTOS benchmark core 2 |
| **VM3** | Linux attack/interference core |

> **Note:** After changing the scenario, a full rebuild is required because the `SCENARIO` macro propagates to multiple components at compile time (Bao config, FreeRTOS tasks, and the Linux VM overlay).
