"""VM2 -> VM0 status relay over the Bao IPC shared-memory region.

A logging.Handler that writes a throttled, compact status line into the shared
IPC window (the same 0x70000000 region ipc_signal uses). The VM0 PMU monitor
reads it and prints it to the serial console. VM2's own console is on a
different UART, so this is how on-board Apparate results reach a single cable.

Inert unless installed: controller.py attaches it only when the environment
variable APPARATE_IPC_RELAY=1 is set, so off-board runs are unaffected.

Text slot layout in the shared region (above the IPC_Channel struct at
offsets 0/4/8/12), little-endian, matching pmu_monitor.c:
    0x100 (u32) seq   -- bumped after each new message (commit marker)
    0x104 (u32) len   -- byte length of the message
    0x108 ...   buf   -- up to TEXT_MAX ASCII bytes
"""
import os
import time
import mmap
import logging

IPC_BASE = 0x70000000
IPC_SIZE = 0x10000
TEXT_SEQ = 0x100
TEXT_LEN = 0x104
TEXT_BUF = 0x108
TEXT_MAX = 200


class IPCRelayHandler(logging.Handler):
    def __init__(self, min_interval=2.0):
        super().__init__()
        self._interval = min_interval
        self._last = 0.0
        fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        try:
            self._map = mmap.mmap(fd, IPC_SIZE, mmap.MAP_SHARED,
                                  mmap.PROT_READ | mmap.PROT_WRITE,
                                  offset=IPC_BASE)
        finally:
            os.close(fd)
        # The region is outside VM2's RAM, so Linux maps it as Device memory,
        # where unaligned accesses fault with SIGBUS (killing the process).
        # mmap slice assignment uses memcpy, which does unaligned stores, so
        # write the text byte by byte and the u32 fields through an aligned
        # 32-bit view.
        self._words = memoryview(self._map).cast("I")

    def emit(self, record):
        now = time.time()
        if now - self._last < self._interval:
            return  # throttle: the serial relay is for a human, not every batch
        self._last = now
        try:
            b = self.format(record).encode("ascii", "replace")[:TEXT_MAX]
            # Write buffer and length first, then bump seq last (the commit).
            # seq is read back and incremented, as ipc_say does, so messages
            # from both writers always change it.
            for i, c in enumerate(b):
                self._map[TEXT_BUF + i] = c
            self._words[TEXT_LEN // 4] = len(b)
            seq = self._words[TEXT_SEQ // 4]
            self._words[TEXT_SEQ // 4] = (seq + 1) & 0xFFFFFFFF
        except Exception:
            pass  # never let logging crash serving
