#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define IPC_PROXY_ADDR 0x70000000
#define IPC_SIZE       0x00100000 // 1MB

// The PC server IP address (user needs to configure this or pass as argument)
// Example: "192.168.1.100"
#define DEFAULT_PC_IP "192.168.0.10"
#define PC_PORT 8080

typedef struct {
    volatile uint32_t signal_ready; // VM0 -> VM3
    volatile uint32_t resume;       // VM3 -> VM0
    volatile uint32_t split_k;
    volatile uint32_t tensor_size;
    uint8_t payload[];
} Proxy_IPC_Channel;

int main(int argc, char *argv[]) {
    const char *pc_ip = DEFAULT_PC_IP;
    if (argc > 1) {
        pc_ip = argv[1];
    }

    int mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem_fd < 0) {
        perror("open /dev/mem");
        return 1;
    }

    void *mapped_base = mmap(NULL, IPC_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, mem_fd, IPC_PROXY_ADDR);
    if (mapped_base == MAP_FAILED) {
        perror("mmap");
        close(mem_fd);
        return 1;
    }

    Proxy_IPC_Channel *ipc = (Proxy_IPC_Channel *)mapped_base;
    printf("Proxy started. Waiting for VM0 inferences. PC Server=%s:%d\n", pc_ip, PC_PORT);

    // Create a single persistent socket or reconnect every time?
    // Connecting per inference adds latency. We will try a persistent connection.
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in serv_addr;
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(PC_PORT);
    inet_pton(AF_INET, pc_ip, &serv_addr.sin_addr);

    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        printf("Connection to PC Server failed. Make sure the server is running.\n");
        // We will continue anyway, just simulating for Phase 1
        sock = -1;
    } else {
        printf("Connected to PC Server.\n");
    }

    while (1) {
        if (ipc->signal_ready == 1) {
            uint32_t k = ipc->split_k;
            uint32_t size = ipc->tensor_size;
            
            printf("Received split_k=%u, size=%u bytes. Forwarding...\n", k, size);

            if (sock != -1) {
                // Send metadata
                uint32_t meta[2] = {k, size};
                send(sock, meta, sizeof(meta), 0);
                
                // Send payload
                send(sock, (void*)ipc->payload, size, 0);
                
                // Receive ack / result
                uint32_t ack = 0;
                recv(sock, &ack, sizeof(ack), 0);
            } else {
                // Simulate network delay if disconnected (1ms per 10KB)
                usleep((size / 10240) * 1000); 
            }

            printf("Roundtrip finished. Resuming VM0.\n");

            // Signal VM0
            ipc->signal_ready = 0;
            __sync_synchronize();
            ipc->resume = 1;
        } else {
            usleep(1000); // 1ms polling
        }
    }

    return 0;
}
