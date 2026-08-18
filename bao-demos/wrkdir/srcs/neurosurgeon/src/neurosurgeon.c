#include "neurosurgeon.h"
#include <stdio.h>

void ns_init(NeurosurgeonState *ns) {
    // 1. Initialize EMA arrays to 0 (will be populated during first inference)
    for (int i = 0; i < NS_NUM_SPLITS; i++) {
        ns->cycles_ema[i] = 0.0f;
    }

    // 2. Load static activation sizes (bytes) based on standard ResNet splitting
    // Values extracted from output tensors of blocks 0..4
    ns->activation_bytes[0] = 802816; // 64 * 56 * 56 * 4
    ns->activation_bytes[1] = 802816; // 64 * 56 * 56 * 4
    ns->activation_bytes[2] = 401408; // 128 * 28 * 28 * 4
    ns->activation_bytes[3] = 200704; // 256 * 14 * 14 * 4
    ns->activation_bytes[4] = 4000;   // 1000 * 4 (final FC output)

    // 3. Load static server compute time profiling (ms)
    // These are offline pre-measured baseline times on a standard PC
    // We only need the time to execute blocks k*+1 ... 4
    // t_server_ms[k] is the time the server takes if we split at k
    ns->t_server_ms[0] = 45.0f; // Server runs blocks 1,2,3,4
    ns->t_server_ms[1] = 30.0f; // Server runs blocks 2,3,4
    ns->t_server_ms[2] = 18.0f; // Server runs blocks 3,4
    ns->t_server_ms[3] = 8.0f;  // Server runs block 4
    ns->t_server_ms[4] = 0.0f;  // Edge does everything, server does 0

    // Initial bandwidth estimate: 10 MB/s (10,000 bytes/ms)
    ns->bw_bytes_per_ms = 10000.0f;
    ns->best_split = NS_NUM_SPLITS - 1; // Default to full edge processing
}

int ns_select_split(NeurosurgeonState *ns, uint64_t timer_freq) {
    int best_k = -1;
    float min_total_time = 9999999.0f;
    float cycles_per_ms = (float)timer_freq / 1000.0f;

    // k represents the split point. 
    // Edge runs blocks 0..k
    // Server runs blocks k+1..4
    for (int k = 0; k < NS_NUM_SPLITS; k++) {
        // 1. T_edge(k) = sum of edge times up to k
        float t_edge_ms = 0.0f;
        for (int i = 0; i <= k; i++) {
            t_edge_ms += ns->cycles_ema[i] / cycles_per_ms;
        }

        // 2. T_comm(k) = Activation_size(k) / Bandwidth
        float t_comm_ms = (float)ns->activation_bytes[k] / ns->bw_bytes_per_ms;

        // 3. T_server(k) = Remaining compute time on server
        float t_server_ms = ns->t_server_ms[k];

        float total_time = t_edge_ms + t_comm_ms + t_server_ms;

        // printf("Split %d: Edge=%.2fms Comm=%.2fms Server=%.2fms Total=%.2fms\n", 
        //         k, t_edge_ms, t_comm_ms, t_server_ms, total_time);

        if (total_time < min_total_time) {
            min_total_time = total_time;
            best_k = k;
        }
    }

    ns->best_split = best_k;
    return best_k;
}

void ns_update_cycles(NeurosurgeonState *ns, int block, uint64_t cycles) {
    if (block < 0 || block >= NS_NUM_SPLITS) return;
    
    if (ns->cycles_ema[block] == 0.0f) {
        ns->cycles_ema[block] = (float)cycles; // First sample
    } else {
        ns->cycles_ema[block] = (1.0f - NS_ALPHA) * ns->cycles_ema[block] + NS_ALPHA * (float)cycles;
    }
}

void ns_update_bandwidth(NeurosurgeonState *ns, uint32_t bytes, float rtt_ms) {
    if (rtt_ms <= 0.001f) return;
    float current_bw = (float)bytes / rtt_ms;
    
    // EMA update for bandwidth too
    ns->bw_bytes_per_ms = (1.0f - NS_ALPHA) * ns->bw_bytes_per_ms + NS_ALPHA * current_bw;
}
