#include "../inc/pmu_monitor.h"
#include "../../VMs/vm_0/src/tasks/inc/globals.h"
#include <stdio.h>

// Include regulation.h for access to SCENARIO, EXEC_VM_x, labels
#include "regulation.h"

#define MAX_SAMPLES 512

static FANN_sample pmu_history[MAX_SAMPLES];
static uint32_t current_sample_index = 0;

//==============================================================================
// IPC — isolated channels (VM0 accesses active ones per scenario)
//==============================================================================
#define IPC_VM1_ADDR 0x70000000   // Channel 0: VM0 <-> VM1
#define IPC_VM2_ADDR 0x70020000   // Channel 1: VM0 <-> VM2
#if EXEC_VM_2 && EXEC_VM_3
#define IPC_VM3_ADDR 0x70040000   // Channel 2: VM0 <-> VM3 (scenario 6: separate channel)
#else
#define IPC_VM3_ADDR 0x70020000   // Channel 1: VM0 <-> VM3 (scenario 3: no VM2)
#endif

typedef struct {
    volatile uint32_t signal_ready;   // VMx -> VM0: "pause done"
    volatile uint32_t resume;         // VM0 -> VMx: "may continue"
    volatile uint32_t current_label;  // VMx -> VM0: attack/benchmark label
} IPC_Channel;

// Labels stored locally by VM0
// Labels are defined at compile time by SCENARIO_LABEL_BENCH / SCENARIO_LABEL_ATTACK
// (see regulation.h)

// Cache helpers to maintain coherency with Linux which uses Uncached Memory
static inline void cache_clean_invalidate(volatile void* addr) {
    asm volatile("dc civac, %0" : : "r" (addr) : "memory");
    asm volatile("dsb sy" ::: "memory");
}

// Initialize IPC regions with zeros (called once at startup)
void ipc_init_channels(void) {
#if EXEC_VM_1
    IPC_Channel* ch_vm1 = (IPC_Channel*) IPC_VM1_ADDR;
    ch_vm1->signal_ready = 0;
    ch_vm1->resume = 0;
    ch_vm1->current_label = 0;
    cache_clean_invalidate((void*)ch_vm1);
#endif

#if EXEC_VM_2
    IPC_Channel* ch_vm2 = (IPC_Channel*) IPC_VM2_ADDR;
    ch_vm2->signal_ready = 0;
    ch_vm2->resume = 0;
    ch_vm2->current_label = 0;
    cache_clean_invalidate((void*)ch_vm2);
#endif

#if EXEC_VM_3
    IPC_Channel* ch_vm3 = (IPC_Channel*) IPC_VM3_ADDR;
    ch_vm3->signal_ready = 0;
    ch_vm3->resume = 0;
    ch_vm3->current_label = 0;
    cache_clean_invalidate((void*)ch_vm3);
#endif
}

void dump_history_to_serial(void) {
    if (current_sample_index == 0) {
        return;
    }

    // Read timer frequency to convert ticks to time
    uint64_t timer_freq;
    asm volatile("mrs %0, cntfrq_el0" : "=r"(timer_freq));

    // BUILD_EPOCH is injected by the Makefile via -DBUILD_EPOCH=$(date +%s)
    // Represents the Unix timestamp of the compilation moment
    // Used as offset to calculate the real time
    #ifndef BUILD_EPOCH
    #define BUILD_EPOCH 0
    #endif
    const uint64_t build_epoch_secs = (uint64_t)BUILD_EPOCH;

    printf("==================================================\n");
    printf("START_OF_CSV_DATA\n");
    printf("CORE_ID,TIMESTAMP,CPU_CYCLES,INSTRUCTIONS,CACHE_MISSES,BRANCH_MISSES,L2_CACHE_ACCESS,LABEL,DET_STATUS,DET_PROB,BENCH_ID,EXIT_USED,CYCLES_SPENT\n");

    for (uint32_t i = 0; i < current_sample_index; i++) {
        // Convert timestamp (ticks) to real time
        uint64_t ticks = pmu_history[i].data.timestamp;
        uint64_t elapsed_ms = (ticks * 1000) / timer_freq;
        uint64_t elapsed_secs = elapsed_ms / 1000;
        uint32_t ms = (uint32_t)(elapsed_ms % 1000);

        // Add boot time to compilation epoch to get real time
        uint64_t total_secs = build_epoch_secs + elapsed_secs;

        // Extract HH:MM:SS from time of day (mod 24h)
        // Timezone adjustment: -3h for BRT (Brasília)
        uint64_t day_secs = (total_secs - 3 * 3600) % 86400;
        uint32_t hh = (uint32_t)(day_secs / 3600);
        uint32_t mm = (uint32_t)((day_secs % 3600) / 60);
        uint32_t ss = (uint32_t)(day_secs % 60);

        // Unpack status, exit_used, and cycles_spent from the packed det_status
        uint64_t raw_det_status = pmu_history[i].data.det_status;
        uint64_t status = raw_det_status & 0xFF;
        uint64_t exit_used = (raw_det_status >> 8) & 0xFF;
        uint64_t cycles_spent = (raw_det_status >> 16) & 0xFFFFFFFF;

        printf("%lu,%02lu:%02lu:%02lu:%03lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            pmu_history[i].core_id,
            (unsigned long)hh, (unsigned long)mm,
            (unsigned long)ss, (unsigned long)ms,
            pmu_history[i].data.cpu_cycles,
            pmu_history[i].data.instructions,
            pmu_history[i].data.cache_misses,
            pmu_history[i].data.branch_misses,
            pmu_history[i].data.l2_cache_access,
            (unsigned long)pmu_history[i].label,
            (unsigned long)status,
            pmu_history[i].data.det_probability_pct,
            (unsigned long)pmu_history[i].bench_id,
            (unsigned long)exit_used,
            (unsigned long)cycles_spent);
    }

    printf("END_OF_CSV_DATA\n");
    printf("==================================================\n");
    fflush(stdout);

    current_sample_index = 0;
}

unsigned long hypercall(unsigned long hc_id, unsigned long arg) {
    const unsigned long full_id = SMCC64_FID_VND_HYP_SRVC | hc_id;

    register unsigned long r0 asm("x0") = full_id;
    register unsigned long r1 asm("x1") = arg;
  
    asm volatile(
        "hvc #0"
        : "+r"(r0)
        : "r"(r1)
        : "memory", "x2", "x3"
    );
    return r0;
}

void bao_get_pmu_data(uint8_t target_cpu, PMU_data *data) {
    const unsigned long full_id = SMCC64_FID_VND_HYP_SRVC | HC_SEC_MONITOR;
  
    register unsigned long r0 asm("x0") = full_id;
    register unsigned long r1 asm("x1") = target_cpu; 
    register unsigned long r2 asm("x2");
    register unsigned long r3 asm("x3");
    register unsigned long r4 asm("x4");
    register unsigned long r5 asm("x5");
    register unsigned long r6 asm("x6");
    register unsigned long r7 asm("x7");
  
    asm volatile(
        "hvc #0"
        : "+r"(r0), "+r"(r1), "=r"(r2), "=r"(r3), "=r"(r4), "=r"(r5), "=r"(r6), "=r"(r7)
        : 
        : "memory"
    ); 
      
    data->cpu_cycles = r0;
    data->cache_misses = r1;
    data->instructions = r2;
    data->branch_misses = r3;
    data->timestamp = r4;
    data->l2_cache_access = r5;
    data->det_status = r6;
    data->det_probability_pct = r7;
}

void collect_and_process_pmu_sample(uint64_t timer_freq) {
#if EXEC_VM_1
    IPC_Channel* ch_vm1 = (IPC_Channel*) IPC_VM1_ADDR;
#endif
#if EXEC_VM_2
    IPC_Channel* ch_vm2 = (IPC_Channel*) IPC_VM2_ADDR;
#endif
#if EXEC_VM_3
    IPC_Channel* ch_vm3 = (IPC_Channel*) IPC_VM3_ADDR;
#endif

    // Force read by flushing/invalidating the cache line
#if EXEC_VM_1
    cache_clean_invalidate((void*)ch_vm1);
#endif
#if EXEC_VM_2
    cache_clean_invalidate((void*)ch_vm2);
#endif
#if EXEC_VM_3
    cache_clean_invalidate((void*)ch_vm3);
#endif

    // Scenario labels are defined at compile time
    // (SCENARIO_LABEL_BENCH / SCENARIO_LABEL_ATTACK in regulation.h)

    // Check barrier: ALL active VMs have signaled?
    int all_ready = 1;
#if EXEC_VM_1
    if (ch_vm1->signal_ready != 1) all_ready = 0;
#endif
#if EXEC_VM_2
    if (ch_vm2->signal_ready != 1) all_ready = 0;
#endif
#if EXEC_VM_3
    if (ch_vm3->signal_ready != 1) all_ready = 0;
#endif

    if (all_ready) {
        // Print the collected data
        dump_history_to_serial();

        // Reset signals and signal resume for active VMs
#if EXEC_VM_1
        ch_vm1->signal_ready = 0;
        ch_vm1->resume = 1;
        cache_clean_invalidate((void*)ch_vm1);
#endif
#if EXEC_VM_2
        ch_vm2->signal_ready = 0;
        ch_vm2->resume = 1;
        cache_clean_invalidate((void*)ch_vm2);
#endif
#if EXEC_VM_3
        ch_vm3->signal_ready = 0;
        ch_vm3->resume = 1;
        cache_clean_invalidate((void*)ch_vm3);
#endif

        return;
    }

    // Normal PMU collection — store in history
    // Only collect from cores that have active VMs
    if (current_sample_index < MAX_SAMPLES) {
        // Single timestamp for all cores in this collection round
        // Read from VM0's cntvct_el0 (global timer shared by all cores)
        uint64_t collection_timestamp;
        asm volatile("isb \n mrs %0, cntvct_el0" : "=r"(collection_timestamp));

        // Physical core → VM mapping (per cpu_affinity in rpi4.c):
        //   Physical core 0 = VM0 (cpu_affinity=0b1)   → monitor (no collection)
        //   Physical core 1 = VM1 (cpu_affinity=0b10)  → benchmarks
        //   Physical core 3 = VM3 (cpu_affinity=0b1000) → Linux (attacks)
        // ── Dynamic label (scenario 7) ──
        // When VM3 is running benchmarks (current_label 1-7), all VMs get label=0
        // When VM3 is attacking (current_label>=10), VM1/VM2=SCENARIO_LABEL_BENCH, VM3=SCENARIO_LABEL_ATTACK
#if EXEC_VM_3
        IPC_Channel* ch_vm3_label = (IPC_Channel*) IPC_VM3_ADDR;
        cache_clean_invalidate((void*)ch_vm3_label);
        uint32_t vm3_current = ch_vm3_label->current_label;
        int vm3_attacking = (vm3_current >= 10);  // 10=spectre, 11=armageddon, 12=meltdown
        unsigned long label_bench  = vm3_attacking ? SCENARIO_LABEL_BENCH  : 0;
        unsigned long label_attack = vm3_attacking ? SCENARIO_LABEL_ATTACK : 0;
#else
        unsigned long label_bench  = SCENARIO_LABEL_BENCH;
#endif

#if EXEC_VM_1
        // Collect core 1 (VM1 = benchmarks)
        if (current_sample_index < MAX_SAMPLES) {
            FANN_sample sample;
            sample.core_id = 1;
            bao_get_pmu_data(1, &sample.data);
            sample.data.timestamp = collection_timestamp;  // synchronized timestamp
            sample.label = label_bench;  // dynamic label based on VM3 state
            sample.bench_id = ch_vm1->current_label;  // benchmark ID via IPC
            sample.output = g_label_atual;
            pmu_history[current_sample_index] = sample;
            current_sample_index++;
            xQueueSend(xPmuQueue, &sample, 0);
        }
#endif

#if EXEC_VM_2
        // Collect core 2 (VM2 = benchmarks)
        if (current_sample_index < MAX_SAMPLES) {
            FANN_sample sample;
            sample.core_id = 2;
            bao_get_pmu_data(2, &sample.data);
            sample.data.timestamp = collection_timestamp;  // synchronized timestamp
            sample.label = label_bench;  // dynamic label based on VM3 state
            sample.bench_id = ch_vm2->current_label;  // benchmark ID via IPC
            sample.output = g_label_atual;
            pmu_history[current_sample_index] = sample;
            current_sample_index++;
            xQueueSend(xPmuQueue, &sample, 0);
        }
#endif

#if EXEC_VM_3
        // Collect core 3 (VM3 = Linux attacks)
        if (current_sample_index < MAX_SAMPLES) {
            FANN_sample sample;
            sample.core_id = 3;
            bao_get_pmu_data(3, &sample.data);
            sample.data.timestamp = collection_timestamp;  // synchronized timestamp
            sample.label = label_attack;  // 0 when benchmark, 3 when attacking
            sample.bench_id = vm3_current;  // 1-7=benchmark, 10/11/12=attack
            sample.output = g_label_atual;
            pmu_history[current_sample_index] = sample;
            current_sample_index++;
            xQueueSend(xPmuQueue, &sample, 0);
        }
#endif
    }
}

void init_pmu_registers(void) {
    #define PMU_EVT_INST_RETIRED     0x08
    #define PMU_EVT_L2D_CACHE_REFILL 0x17
    #define PMU_EVT_L2D_CACHE        0x16
    #define PMU_EVT_BR_MIS_PRED      0x10

    asm volatile("msr pmselr_el0, %0" :: "r" (0));
    asm volatile("isb");
    asm volatile("msr pmxevtyper_el0, %0" :: "r" (PMU_EVT_BR_MIS_PRED));

    asm volatile("msr pmselr_el0, %0" :: "r" (1));
    asm volatile("isb");
    asm volatile("msr pmxevtyper_el0, %0" :: "r" (PMU_EVT_L2D_CACHE_REFILL));

    asm volatile("msr pmselr_el0, %0" :: "r" (2));
    asm volatile("isb");
    asm volatile("msr pmxevtyper_el0, %0" :: "r" (PMU_EVT_L2D_CACHE));

    asm volatile("msr pmselr_el0, %0" :: "r" (3));
    asm volatile("isb");
    asm volatile("msr pmxevtyper_el0, %0" :: "r" (PMU_EVT_INST_RETIRED));

    asm volatile("msr pmccfiltr_el0, %0" :: "r" (0));
    asm volatile("msr pmcntenset_el0, %0" : : "r" (0x8000000F));  // bits 0,1,2,3 + cycle counter
    asm volatile("msr pmcr_el0, %0" : : "r" (0x07));
}