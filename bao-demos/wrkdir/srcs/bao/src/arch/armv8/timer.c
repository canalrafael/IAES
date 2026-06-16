#include <bao.h>
#include <arch/sysregs.h>
#include <arch/generic_timer.h>
#include <interrupts.h>
#include <cpu.h>
#include <arch/detector.h>
#include <arch/fp_context.h>

#define MRS(v, r) __asm__ volatile("mrs %0, " #r : "=r" (v))
#define MSR(r, v) __asm__ volatile("msr " #r ", %0" : : "r" (v))
#define ISB()     __asm__ volatile("isb")

#define TIMMER_PERIOD 200000 // 200ms 
#define CNTHP_IRQ 26 // EL2 physical timer IRQ ID

// PMU events
#define PMU_EVT_INST_RETIRED     0x08
#define PMU_EVT_L2D_CACHE_REFILL 0x17
#define PMU_EVT_L2D_CACHE        0x16
#define PMU_EVT_BR_MIS_PRED      0x10

// Bitmask to enable the cycle counter and event counters
#define PMU_ENABLE_ALL  ((1UL << 31) | (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3))

volatile pmu_data_t g_pmu_data[PMU_MAX_CPUS];

// FP context per CPU — protects the NEON/FP registers of the VMs
// during detector execution (which uses float)
static fp_context_t s_fp_ctx[PMU_MAX_CPUS];

// Convert microseconds to timer ticks
static uint64_t us_to_ticks(uint64_t us) {
    uint64_t freq;
    MRS(freq, cntfrq_el0); // sysreg_cntfrq_el0_read
    return (us * freq) / 1000000;
}

static void pmu_init_registers(void) {
    uint64_t val;

    // Disable PMU globally (PMCR.E = 0)
    MRS(val, pmcr_el0);
    val &= ~(1 << 0);
    MSR(pmcr_el0, val);

    // Explicitly disable individual counters
    val = PMU_ENABLE_ALL;
    MSR(pmcntenclr_el0, val); 

    // Configure cycle counter filter — exclude EL2 (bit 27 = NSH)
    // to count only VM cycles (EL1/EL0), not the hypervisor
    #define PMU_FILTER_EXCLUDE_EL2  (1UL << 27)
    __asm__ volatile("msr pmccfiltr_el0, %0" :: "r" (PMU_FILTER_EXCLUDE_EL2));

    // Configure counters using DIRECT registers (avoids indirect pmselr bugs)

    // Counter 0: branch misses — exclude EL2
    __asm__ volatile("msr pmevtyper0_el0, %0" :: "r" ((uint64_t)(PMU_EVT_BR_MIS_PRED | PMU_FILTER_EXCLUDE_EL2)));

    // Counter 1: L2 cache misses (LLC on RPi4) — exclude EL2
    __asm__ volatile("msr pmevtyper1_el0, %0" :: "r" ((uint64_t)(PMU_EVT_L2D_CACHE_REFILL | PMU_FILTER_EXCLUDE_EL2)));

    // Counter 2: L2 cache access (total LLC accesses) — exclude EL2
    __asm__ volatile("msr pmevtyper2_el0, %0" :: "r" ((uint64_t)(PMU_EVT_L2D_CACHE | PMU_FILTER_EXCLUDE_EL2)));

    // Counter 3: instructions — exclude EL2
    __asm__ volatile("msr pmevtyper3_el0, %0" :: "r" ((uint64_t)(PMU_EVT_INST_RETIRED | PMU_FILTER_EXCLUDE_EL2)));

    ISB();

    // Enable counters
    val = PMU_ENABLE_ALL;
    MSR(pmcntenset_el0, val);

    // Reset and global enable
    MRS(val, pmcr_el0);
    val |= (1 << 0) | (1 << 1) | (1 << 2); // Enable, Reset Counters, Reset Cycle
    MSR(pmcr_el0, val);
}

// Read PMU data using DIRECT registers
static inline void pmu_collect_data(void) {
    uint64_t val;

    cpuid_t id = cpu()->id;
    if (id >= PMU_MAX_CPUS) return;

    // CPU cycles
    MRS(val, pmccntr_el0);
    g_pmu_data[id].cpu_cycles = val;

    // Branch misses (Counter 0) — direct access
    __asm__ volatile("mrs %0, pmevcntr0_el0" : "=r" (val));
    g_pmu_data[id].branch_misses = val;

    // Cache misses (Counter 1) — direct access
    __asm__ volatile("mrs %0, pmevcntr1_el0" : "=r" (val));
    g_pmu_data[id].cache_misses = val;

    // L2 cache access (Counter 2) — direct access
    __asm__ volatile("mrs %0, pmevcntr2_el0" : "=r" (val));
    g_pmu_data[id].l2_cache_access = val;

    // Instructions (Counter 3) — direct access
    __asm__ volatile("mrs %0, pmevcntr3_el0" : "=r" (val));
    g_pmu_data[id].instructions = val;

    // Timestamp
    MRS(val, cntpct_el0); 
    g_pmu_data[id].timestamp = val;

    // Reinitialize registers for the next collection
    // (pmu_init_registers() already does full reset and enable)
    pmu_init_registers();
}

void timer_handler(irqid_t irq_id) {
    // Disable the timer temporarily
    uint32_t ctl;
    MRS(ctl, cnthp_ctl_el2);
    ctl |= GENERIC_TIMER_IMASK; 
    MSR(cnthp_ctl_el2, ctl);

    cpuid_t id = cpu()->id;

    // Each core collects and processes its own data independently.
    //
    // FIX: the previous version centralized inference on core 1, which read
    // core 2's data without synchronization guarantees (potentially stale data
    // from the previous interval). Additionally, core 0 was never processed.
    // This version eliminates both problems:
    //   - No inter-core synchronization needed (no risk of stale data).
    //   - All PMU_MAX_CPUS cores are monitored.
    //   - Mirrors exactly the Python pipeline: one row (one core) at a time.
    if (id < PMU_MAX_CPUS) {
        // Step 1: collect PMU data from this core and reset counters,
        // ensuring each sample represents exactly one 200ms interval.
        pmu_collect_data();

        // Step 2: run inference for this core.
        // The detector now has PER-CPU arrays (s_ring[cpu_id]),
        // so no spinlock is needed. 100% parallel execution.
        fp_context_save(&s_fp_ctx[id]);

        pmu_sample_t s = {
            .cpu_cycles      = g_pmu_data[id].cpu_cycles,
            .instructions    = g_pmu_data[id].instructions,
            .cache_misses    = g_pmu_data[id].cache_misses,
            .branch_misses   = g_pmu_data[id].branch_misses,
            .l2_cache_access = g_pmu_data[id].l2_cache_access,
        };

        det_output_t out = detector_process_sample(id, &s);

        // Store the detector result for this core (pack status, exit_used, and cycles_spent)
        g_pmu_data[id].det_status          = (uint64_t)out.status |
                                             ((uint64_t)out.exit_used << 8) |
                                             ((uint64_t)out.cycles_spent << 16);
        g_pmu_data[id].det_probability_pct = (uint64_t)(out.probability * 100);

        // Closed-loop mitigation: if an attack is detected, throttle execution
        // of this CPU dynamically based on the classifier's probability/confidence
        if (out.status == DET_ATTACK) {
            uint64_t base_delay = 5000000; // Base delay loop limit
            volatile uint64_t delay = (uint64_t)(out.probability * base_delay);
            while (delay--) {
                __asm__ volatile("nop");
            }
        }

        fp_context_restore(&s_fp_ctx[id]);
    }

    // Reprogram the next timer firing
    uint64_t current_cnt;
    MRS(current_cnt, cntpct_el0);
    MSR(cnthp_cval_el2, current_cnt + us_to_ticks(TIMMER_PERIOD));

    // Re-enable the timer
    ctl &= ~GENERIC_TIMER_IMASK;
    MSR(cnthp_ctl_el2, ctl);

    // Clear the GIC
    interrupts_arch_clear(irq_id);
}

void timer_arch_init(void) {
    // Initialize PMU registers
    pmu_init_registers();

    // Initialize the interference detector (zeroes internal ring buffers)
    detector_init();

    // Enable the EL2 physical timer
    uint32_t ctl = GENERIC_TIMER_ENABLE;
    MSR(cnthp_ctl_el2, ctl);

    // Set the first timer firing
    uint64_t current_cnt;
    MRS(current_cnt, cntpct_el0);
    MSR(cnthp_cval_el2, current_cnt + us_to_ticks(TIMMER_PERIOD));

    interrupts_reserve(CNTHP_IRQ, timer_handler);
    interrupts_arch_enable(CNTHP_IRQ, true);
}