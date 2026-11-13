"""
Adversarial Stressors and Attack Generators for ANS Split Inference
==================================================================
Implements three attack vectors to stress the collaborative edge system:
1. MemoryContentionStressor:
   Microarchitectural cache & memory bus thrashing on the Raspberry Pi
   (causes Attribution Error in muLinUCB due to slow serialization/copies).
2. CPUStressor:
   Multi-core compute saturation on the Raspberry Pi CPU
   (stresses on-device layer execution).
3. NetworkDelayStressor:
   Injected network latency / jitter / bandwidth bottleneck on offloading.
"""

import multiprocessing
import os
import time
from typing import List, Optional
import numpy as np


# ----------------------------------------------------------------------
# 1. Microarchitectural Memory Contention Stressor (from IAES)
# ----------------------------------------------------------------------
def _memory_contention_worker(stop_event: multiprocessing.Event, buffer_mb: int = 32) -> None:
    """
    Continuously reads and writes large memory blocks exceeding the CPU cache
    (RPi 4 has 1 MB shared L2), causing heavy cache eviction and memory bus saturation.
    """
    elements = (buffer_mb * 1024 * 1024) // 4
    arr1 = np.ones(elements, dtype=np.float32)
    arr2 = np.ones(elements, dtype=np.float32)

    while not stop_event.is_set():
        arr1 += arr2
        arr2 *= 1.0001
        np.copyto(arr1, arr2)


class MemoryContentionStressor:
    def __init__(self, num_workers: int = 4, buffer_mb: int = 32):
        self.num_workers = num_workers
        self.buffer_mb = buffer_mb
        self._stop_event: Optional[multiprocessing.Event] = None
        self._workers: List[multiprocessing.Process] = []
        self.is_active = False

    def start(self) -> None:
        if self.is_active:
            return
        self._stop_event = multiprocessing.Event()
        self._workers = []
        for _ in range(self.num_workers):
            p = multiprocessing.Process(
                target=_memory_contention_worker,
                args=(self._stop_event, self.buffer_mb),
                daemon=True
            )
            p.start()
            self._workers.append(p)
        self.is_active = True
        print(f"[ATTACK: MemoryContention] Started with {self.num_workers} workers ({self.buffer_mb}MB each).")

    def stop(self) -> None:
        if not self.is_active:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        for p in self._workers:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        self._workers.clear()
        self._stop_event = None
        self.is_active = False
        print("[ATTACK: MemoryContention] Stopped.")


# ----------------------------------------------------------------------
# 2. CPU Compute Saturation Stressor
# ----------------------------------------------------------------------
def _cpu_stress_worker(stop_event: multiprocessing.Event) -> None:
    """
    Worker process running tight matrix multiplication loops to pin CPU cores to 100%.
    """
    size = 256
    while not stop_event.is_set():
        a = np.random.rand(size, size).astype(np.float32)
        b = np.random.rand(size, size).astype(np.float32)
        _ = np.dot(a, b)


class CPUStressor:
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self._stop_event: Optional[multiprocessing.Event] = None
        self._workers: List[multiprocessing.Process] = []
        self.is_active = False

    def start(self) -> None:
        if self.is_active:
            return
        self._stop_event = multiprocessing.Event()
        self._workers = []
        for _ in range(self.num_workers):
            p = multiprocessing.Process(
                target=_cpu_stress_worker,
                args=(self._stop_event,),
                daemon=True
            )
            p.start()
            self._workers.append(p)
        self.is_active = True
        print(f"[ATTACK: CPUStress] Started with {self.num_workers} CPU workers.")

    def stop(self) -> None:
        if not self.is_active:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        for p in self._workers:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        self._workers.clear()
        self._stop_event = None
        self.is_active = False
        print("[ATTACK: CPUStress] Stopped.")


# ----------------------------------------------------------------------
# 3. Network Delay / Degradation Stressor
# ----------------------------------------------------------------------
class NetworkDelayStressor:
    """
    Injects artificial network delay (RTT degradation) or simulated bandwidth throttling
    during socket send/receive operations.
    """
    def __init__(self, injected_delay_ms: float = 250.0, jitter_ms: float = 50.0):
        self.injected_delay_ms = injected_delay_ms
        self.jitter_ms = jitter_ms
        self.is_active = False

    def start(self) -> None:
        self.is_active = True
        print(f"[ATTACK: NetworkDelay] Started (+{self.injected_delay_ms}ms RTT delay).")

    def stop(self) -> None:
        self.is_active = False
        print("[ATTACK: NetworkDelay] Stopped.")

    def apply_delay(self) -> float:
        """Applies injected network sleep if active, returning added delay in seconds."""
        if not self.is_active:
            return 0.0
        jitter = np.random.uniform(-self.jitter_ms, self.jitter_ms)
        delay_sec = max(0.01, (self.injected_delay_ms + jitter) / 1000.0)
        time.sleep(delay_sec)
        return delay_sec


# ----------------------------------------------------------------------
# Factory Function
# ----------------------------------------------------------------------
def create_stressor(attack_type: str, num_workers: int = 4):
    """Creates a stressor instance by name."""
    attack_type = attack_type.lower()
    if attack_type == 'memory':
        return MemoryContentionStressor(num_workers=num_workers, buffer_mb=32)
    elif attack_type == 'cpu':
        return CPUStressor(num_workers=num_workers)
    elif attack_type == 'network':
        return NetworkDelayStressor(injected_delay_ms=250.0, jitter_ms=50.0)
    else:
        raise ValueError(f"Unknown attack type: {attack_type}. Choose 'memory', 'cpu', or 'network'.")
