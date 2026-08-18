#include <iostream>
#include <vector>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <string.h>

#define PORT 8080

// Stub for ncnn
// #include "ncnn/net.h"

int main() {
    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);

    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("socket failed");
        exit(EXIT_FAILURE);
    }

    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt))) {
        perror("setsockopt");
        exit(EXIT_FAILURE);
    }
    
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }
    
    if (listen(server_fd, 3) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }
    
    std::cout << "PC Server listening on port " << PORT << "..." << std::endl;

    // Load ncnn models (blocks 1 to 4)
    // ncnn::Net blocks[5];
    // blocks[1].load_param("block1.param"); blocks[1].load_model("block1.bin");
    // ...

    while (true) {
        if ((new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
            perror("accept");
            continue;
        }

        std::cout << "VM3 Proxy connected." << std::endl;

        while (true) {
            uint32_t meta[2];
            int valread = recv(new_socket, meta, sizeof(meta), MSG_WAITALL);
            if (valread <= 0) break; // Disconnected

            uint32_t split_k = meta[0];
            uint32_t size = meta[1];

            std::cout << "Received inference split_k=" << split_k << " size=" << size << std::endl;

            std::vector<uint8_t> payload(size);
            valread = recv(new_socket, payload.data(), size, MSG_WAITALL);
            if (valread <= 0) break;

            // [Phase 2] Load tensor into ncnn::Mat and run remaining blocks
            // ncnn::Mat in(w, h, c, payload.data());
            // ncnn::Extractor ex = blocks[split_k+1].create_extractor();
            // ...

            // Send Ack / result
            uint32_t ack = 1;
            send(new_socket, &ack, sizeof(ack), 0);
        }
        
        std::cout << "VM3 Proxy disconnected. Waiting for new connection..." << std::endl;
        close(new_socket);
    }

    return 0;
}
