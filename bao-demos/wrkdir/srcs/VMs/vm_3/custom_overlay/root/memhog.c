/* memhog - saturate memory bandwidth to contend with co-located VMs.
 *
 * Pure resource contention, NOT a side-channel: it just streams large arrays
 * (>> the 1 MB L2) so it is DRAM-bandwidth bound. With Bao cache coloring the
 * L2 is partitioned between VMs, but the memory bus is shared, so this is the
 * channel a neighbour saturates to slow the victim's memory accesses.
 *
 * Usage: memhog [delay_seconds]
 *   delay_seconds: wait before starting (default 0), so the victim VM can
 *   calibrate a clean, uncontended latency baseline first.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>

#define SZ (64u * 1024 * 1024)   /* 64 MB, far larger than the L2 */

int main(int argc, char *argv[]) {
    unsigned delay = (argc > 1) ? (unsigned)atoi(argv[1]) : 0;
    if (delay) sleep(delay);

    uint8_t *a = malloc(SZ);
    uint8_t *b = malloc(SZ);
    if (!a || !b) { perror("malloc"); return 1; }
    memset(a, 1, SZ);
    memset(b, 2, SZ);

    for (;;) {
        memcpy(a, b, SZ);                       /* streaming read + write */
        uint64_t s = 0;
        for (size_t i = 0; i < SZ; i += 64)     /* strided read, one per cache line */
            s += a[i];
        if (s == 0xDEADBEEFu) putchar((int)s);  /* keep the reads from being optimized out */
    }
    return 0;
}
