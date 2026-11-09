"""Live latency source for the on-board contention experiment (Etapa 2).

The Apparate controller replays conf/acc traces and never times real work, so
on its own it cannot feel contention from a co-located VM. This module gives it
a live signal:

  * A background probe thread times a memory-bound op (a strided reduction whose
    working set far exceeds the LLC, so it is bound by DRAM bandwidth). With
    cache coloring on, the LLC is partitioned but the memory bus is NOT, so this
    is exactly the channel a neighbour VM saturates. Each window takes the
    MINIMUM of N quick trials, which filters CPU-scheduling jitter (VM2 has one
    core shared by the controller and the probe) and leaves the bus-contention
    component. s_mem(t) = window_min / global_min_baseline, so s_mem >= 1, and
    s_mem == 1 while a clean (uncontended) window exists -- which is why the
    neighbour must leave a clean startup window before it starts contending.

  * `make_source(probe)` returns a Controller._latency_source that scales each
    ramp's vanilla *prefix* latency DEPTH-RAMPED: the earliest (memory-bound)
    layers by s_mem, the last by 1.0, leaving the small ramp-head overheads
    alone. A uniform slowdown cancels in Apparate's ratio formulas and moves no
    decision; the early-vs-late differential is what shifts the controller.
"""
import time
import threading

import numpy as np


class ContentionProbe(threading.Thread):
    def __init__(self, interval=1.0, mem_mb=16, trials=5, logger=None):
        super().__init__(daemon=True)
        self._interval = interval
        self._trials = trials
        # Working set >> LLC (A72 L2 is 1 MB): DRAM-bandwidth bound.
        self._mem = np.ones((mem_mb * 1024 * 1024) // 8, dtype=np.float64)
        self._base = None          # global minimum memory-op time (clean baseline)
        self.s_mem = 1.0
        self._logger = logger
        self._stop = threading.Event()

    def _time_mem_once(self):
        t = time.perf_counter()
        # strided read defeats the prefetcher so each access pays DRAM latency
        _ = self._mem[::8].sum()
        return time.perf_counter() - t

    def run(self):
        while not self._stop.is_set():
            window_min = min(self._time_mem_once() for _ in range(self._trials))
            self._base = window_min if self._base is None else min(self._base, window_min)
            self.s_mem = max(1.0, window_min / self._base)
            if self._logger is not None:
                self._logger.info("live_latency s_mem=%.3f (base=%.4gs)", self.s_mem, self._base)
            self._stop.wait(self._interval)

    def stop(self):
        self._stop.set()


def make_source(probe):
    """Controller._latency_source driven by the probe's measured slowdown.

    Depth-ramped prefix scaling: first ramp by s_mem, last by 1.0; ramp-head
    overheads untouched.
    """
    def source(batch_size, profile):
        n = len(profile)
        if n <= 1:
            return list(profile)
        s = probe.s_mem
        out = []
        for i, (prefix, overhead) in enumerate(profile):
            frac = i / (n - 1)
            factor = s + (1.0 - s) * frac   # s at the earliest ramp, 1.0 at the last
            out.append((prefix * factor, overhead))
        return out
    return source


def install(controller, logger=None, interval=1.0):
    """Start the probe and attach the live source to a Controller."""
    probe = ContentionProbe(interval=interval, logger=logger)
    probe.start()
    controller._latency_source = make_source(probe)
    return probe


if __name__ == "__main__":
    # Math self-test (no board): a fake probe with fixed slowdown.
    class FakeProbe:
        s_mem = 3.0
    prof = [(10.0, 1.0), (20.0, 1.0), (30.0, None)]
    out = make_source(FakeProbe())(4, prof)
    # early prefix *3, mid *2, last *1; overheads untouched
    assert out == [(30.0, 1.0), (40.0, 1.0), (30.0, None)], out

    class NoContention:
        s_mem = 1.0
    assert make_source(NoContention())(4, prof) == prof  # s=1 -> baseline unchanged
    print("live_latency math self-test OK")
