#include "FreeRTOS.h"
#include "task.h"
#include <stdio.h>
#include "../../../neurosurgeon/inc/neurosurgeon.h"
#include "globals.h"

// The expanded IPC channel to VM3 is at 0x70000000 (Scenario 2) or 0x70200000 (Scenario 6)
// We will use 0x70000000 as the base for the proxy channel.
#define IPC_PROXY_ADDR 0x70000000

typedef struct {
    volatile uint32_t signal_ready; // VM0 -> VM3
    volatile uint32_t resume;       // VM3 -> VM0
    volatile uint32_t split_k;      // Split point selected by VM0
    volatile uint32_t tensor_size;  // Size of tensor
    uint8_t payload[];              // Tensor data
} Proxy_IPC_Channel;

static inline void cache_clean_invalidate(volatile void* addr, size_t size) {
    uintptr_t p = (uintptr_t)addr & ~(64 - 1);
    uintptr_t end = (uintptr_t)addr + size;
    for (; p < end; p += 64) {
        asm volatile("dc civac, %0" : : "r" (p) : "memory");
    }
    asm volatile("dsb sy" ::: "memory");
}

void task_inference(void *arg) {
    NeurosurgeonState ns;
    ns_init(&ns);

    uint64_t timer_freq = get_hardware_timer_freq();
    Proxy_IPC_Channel* ipc = (Proxy_IPC_Channel*) IPC_PROXY_ADDR;
    
    printf("Neurosurgeon Inference Task started.\n");
    
    while(1) {
        // 1. Controller: Decide split point
        int k = ns_select_split(&ns, timer_freq);
        
        // 2. Execute blocks up to k
        uint64_t start_cycles = get_hardware_timer_count();
        
        // MOCK EXECUTION: In phase 2, this will be replaced with ncnn C-API calls
        // For Phase 1 (validation), we mock the computation delay
        vTaskDelay(pdMS_TO_TICKS(10 * (k+1))); 
        
        uint64_t end_cycles = get_hardware_timer_count();
        
        // 3. Update controller EMA for this inference
        ns_update_cycles(&ns, k, end_cycles - start_cycles);
        
        // 4. Send to proxy (VM3)
        uint32_t tensor_size = ns.activation_bytes[k];
        ipc->split_k = k;
        ipc->tensor_size = tensor_size;
        ipc->signal_ready = 1;
        ipc->resume = 0;
        cache_clean_invalidate(ipc, sizeof(Proxy_IPC_Channel) + 64);
        
        // Wait for VM3 Proxy to acknowledge and finish server roundtrip
        uint64_t t_send = get_hardware_timer_count();
        
        while(ipc->resume == 0) {
            cache_clean_invalidate(ipc, sizeof(Proxy_IPC_Channel));
            vTaskDelay(pdMS_TO_TICKS(1)); 
        }
        
        uint64_t t_recv = get_hardware_timer_count();
        float rtt_ms = (float)(t_recv - t_send) * 1000.0f / timer_freq;
        
        // 6. Update Bandwidth estimate
        ns_update_bandwidth(&ns, tensor_size, rtt_ms);
        
        // Clear signal for next round
        ipc->signal_ready = 0;
        cache_clean_invalidate(ipc, sizeof(Proxy_IPC_Channel));
        
        printf("Inference finished: split_k=%d, RTT=%.2fms, BW=%.2f B/ms\n", k, rtt_ms, ns.bw_bytes_per_ms);
        
        vTaskDelay(pdMS_TO_TICKS(1000)); // Run inference once per second
    }
}
