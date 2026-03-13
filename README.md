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

## 🛠 Project Structure
- `/platforms/rpi4`: Configuration files and device trees for the Raspberry Pi 4.
- `/demos`: Source code for the Mixed-Criticality demos (Linux + FreeRTOS).
- `/scripts`: Automation for building and deploying the hypervisor image.
- `.gitignore`: Configured to exclude heavy build artifacts (`wrkdir/`) and binaries.

## 🏗 Build Instructions
To build the default mixed-criticality demo:

```bash
# Initialize submodules (Bao Hypervisor Core)
git submodule update --init --recursive

# Compile for Raspberry Pi 4
make PLATFORM=rpi4 DEMO=linux+freertos
