#ifndef NEUROSURGEON_H
#define NEUROSURGEON_H

#include <stdint.h>
#include <stddef.h>

#define NS_NUM_SPLITS 5
#define NS_ALPHA 0.1f // EMA smoothing factor

typedef struct {
    // Controller inputs / estimates
    float cycles_ema[NS_NUM_SPLITS];       // EMA of cpu_cycles per block
    uint32_t activation_bytes[NS_NUM_SPLITS]; // static: bytes at each split point
    float t_server_ms[NS_NUM_SPLITS];      // static: pre-measured server time (ms)
    
    // Bandwidth estimation
    float bw_bytes_per_ms;                 // current bandwidth estimate (bytes / ms)
    
    // Output
    int best_split;                        // last selected k* (0 to 4)
} NeurosurgeonState;

// Initialize the controller (loads static tables)
void ns_init(NeurosurgeonState *ns);

// Select the optimal split point (k* = 0..4)
// timer_freq is needed to convert cycles to milliseconds for edge computation
int ns_select_split(NeurosurgeonState *ns, uint64_t timer_freq);

// Update EMA for a given block's cycles
void ns_update_cycles(NeurosurgeonState *ns, int block, uint64_t cycles);

// Update Bandwidth estimate based on a transfer
void ns_update_bandwidth(NeurosurgeonState *ns, uint32_t bytes, float rtt_ms);

#endif // NEUROSURGEON_H
