"""
Microarchitectural Contention Generator (Memory & Cache Stressor)
================================================================
Simulates a co-resident adversarial domain generating memory bus
and cache contention (a^probe) to bias the adaptive split controller.
"""

import multiprocessing
import os
import time
from typing import List, Optional
import numpy as np


def _memory_contention_worker(stop_event: multiprocessing.Event, buffer_mb: int = 16) -> None:
    """
    Worker process that continuously reads and writes large memory blocks,
    far exceeding the CPU cache size, causing heavy LLC cache eviction
    and memory bus saturation.
    """
    # Allocate buffer larger than L2/L3 cache (e.g., 16 MB or 32 MB)
    elements = (buffer_mb * 1024 * 1024) // 4
    arr1 = np.ones(elements, dtype=np.float32)
    arr2 = np.ones(elements, dtype=np.float32)

    while not stop_event.is_set():
        # Sequential and strided memory reads/writes to thrash cache and memory bus
        arr1 += arr2
        arr2 *= 1.0001
        np.copyto(arr1, arr2)


class MemoryContentionStressor:
    """
    Controls an array of background contention processes to simulate
    co-resident microarchitectural interference patterns.
    """
    def __init__(self, num_workers: int = 4, buffer_mb: int = 16):
        self.num_workers = num_workers
        self.buffer_mb = buffer_mb
        self._stop_event: Optional[multiprocessing.Event] = None
        self._workers: List[multiprocessing.Process] = []
        self.is_active = False

    def start(self) -> None:
        """Starts the contention burst immediately."""
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

    def stop(self) -> None:
        """Stops the contention burst and restores normal conditions."""
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

    def burst(self, duration_sec: float) -> None:
        """Executes a fixed-duration contention burst."""
        self.start()
        time.sleep(duration_sec)
        self.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
