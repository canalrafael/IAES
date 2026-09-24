#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <string.h>

#define IPC_BASE_ADDR 0x70000000
#define IPC_SIZE      0x10000

// IPC_Channel layout:
// offset 0: signal_ready
// offset 4: resume
// offset 8: current_label

int main(int argc, char *argv[]) {
    if (argc < 3) {
        printf("Usage: %s [write|read] [offset] <value_if_write>\n", argv[0]);
        return 1;
    }

    const char *cmd = argv[1];
    off_t offset = strtol(argv[2], NULL, 0);

    if (offset < 0 || offset >= IPC_SIZE) {
        printf("Invalid offset\n");
        return 1;
    }

    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) {
        perror("open(/dev/mem)");
        return 1;
    }

    void *map = mmap(NULL, IPC_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, IPC_BASE_ADDR);
    if (map == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return 1;
    }

    volatile uint32_t *ptr = (volatile uint32_t *)((char *)map + offset);

    if (strcmp(cmd, "write") == 0) {
        if (argc < 4) {
            printf("Missing value for write\n");
            return 1;
        }
        uint32_t val = strtoul(argv[3], NULL, 0);
        *ptr = val;
    } else if (strcmp(cmd, "read") == 0) {
        uint32_t val = *ptr;
        printf("%u\n", val);
    } else {
        printf("Unknown command: %s\n", cmd);
    }

    munmap(map, IPC_SIZE);
    close(fd);
    return 0;
}
