/* ipc_say — write a text line to the VM2->VM0 relay slot in the shared IPC
 * region, so it prints on VM0's serial console. Pure C (no Python), used by
 * S99apparate to relay boot/env diagnostics even when python3/numpy is the
 * thing that is broken. Slot layout matches ipc_report.py and pmu_monitor.c.
 *
 * Usage: ipc_say "message"
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <string.h>

#define IPC_BASE_ADDR 0x70000000
#define IPC_SIZE      0x10000
#define TEXT_SEQ      0x100
#define TEXT_LEN      0x104
#define TEXT_BUF      0x108
#define TEXT_MAX      200

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <message>\n", argv[0]);
        return 1;
    }

    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("open(/dev/mem)"); return 1; }

    void *map = mmap(NULL, IPC_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, IPC_BASE_ADDR);
    if (map == MAP_FAILED) { perror("mmap"); close(fd); return 1; }
    char *base = (char *)map;

    size_t len = strlen(argv[1]);
    if (len > TEXT_MAX) len = TEXT_MAX;
    /* Byte stores, not memcpy: 0x70000000 is outside VM2's RAM, so /dev/mem
     * maps it as Device memory, where glibc memcpy's unaligned stores fault
     * (SIGBUS) and the message is never committed. */
    volatile uint8_t *buf = (volatile uint8_t *)(base + TEXT_BUF);
    for (size_t i = 0; i < len; i++)
        buf[i] = (uint8_t)argv[1][i];
    *(volatile uint32_t *)(base + TEXT_LEN) = (uint32_t)len;
    uint32_t seq = *(volatile uint32_t *)(base + TEXT_SEQ);
    *(volatile uint32_t *)(base + TEXT_SEQ) = seq + 1;  /* commit last */

    msync(map, IPC_SIZE, MS_SYNC);
    munmap(map, IPC_SIZE);
    close(fd);
    return 0;
}
