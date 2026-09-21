// Filename: regulation.h
// Author: Everaldo Pereira Gomes

#ifndef REGULATION_H
#define REGULATION_H

#include <stdint.h>

#define DEBUG 0

// =======================================
// Do not change below
// =======================================
#define UNUSED_ARG 0
#define UNUSED_VALUE 4294967295U
#define MAX_INT 4294967295U

#define NO 0
#define YES 1

#define READ 0
#define WRITE 1

#define PMU_COUNTER_PAIR_RW 0

#define PMU_0_OVERFLOWED_ID 0
#define PMU_1_OVERFLOWED_ID 1

// #define GUEST_RESUME_TASK_0_ID 0
// #define GUEST_SUSPEND_TASK_0_BUDGET_ID 1
//
// #define GUEST_RESUME_TASK_1_ID 2
// #define GUEST_SUSPEND_TASK_1_BUDGET_ID 3

#define VM_0 0
#define VM_1 1
#define VM_2 2
#define VM_3 3

#define OTHER_TASK_PRIORITY 0
#define CTRL_TASK_PRIORITY 1

// #define TASK_0 0
// #define TASK_1 1
//
// #define TASK_PRIORITY_0 0
// #define TASK_PRIORITY_1 1
// #define TASK_PRIORITY_2 2
// #define TASK_PRIORITY_3 3
// #define TASK_PRIORITY_4 4
// #define TASK_PRIORITY_5 5
// #define TASK_PRIORITY_6 6
// #define TASK_PRIORITY_7 7

#define PMU_COUNT 6
#define PMU_COUNTER_0 0
#define PMU_COUNTER_1 1
#define PMU_COUNTER_2 2
#define PMU_COUNTER_3 3
#define PMU_COUNTER_4 4
#define PMU_COUNTER_5 5

// #define BENCHMARK_BANDWIDTH 0
// #define BENCHMARK_DISPARITY 1
// #define BENCHMARK_MSER 2
// #define BENCHMARK_FFT 3
// #define BENCHMARK_SORTING 4
// #define BENCHMARK_QSORT 5
// #define BENCHMARK_DIJKSTRA 6
// #define BENCHMARK_SHA 7

#define TASK_STACK_SIZE 400
// #define BANDWIDTH_TASK_STACK_SIZE 400
// #define DISPARITY_TASK_STACK_SIZE 400
// #define MSER_TASK_STACK_SIZE 400
// #define FFT_TASK_STACK_SIZE 400
// #define SORTING_TASK_STACK_SIZE 400
// #define QSORT_TASK_STACK_SIZE 400
// #define DIJKSTRA_TASK_STACK_SIZE 400
// #define SHA_TASK_STACK_SIZE 400
//
// #define BANDWIDTH_TASK_NAME "Bandwidth_task"
// #define DISPARITY_TASK_NAME "Disparity_task"
// #define MSER_TASK_NAME "MSER_task"
// #define FFT_TASK_NAME "FFT_task"
// #define SORTING_TASK_NAME "Sorting_task"
// #define QSORT_TASK_NAME "QSort_task"
// #define DIJKSTRA_TASK_NAME "Dijkstra_task"
// #define SHA_TASK_NAME "SHA_task"
// =======================================
// End of do-not-change section
// =======================================

#define PERIOD_QNT 10

// ===== DATA COLLECTION SCENARIO SELECTION =====
// Scenario 1: Benchmarks only on 1 core, sequential (label 0)
// Scenario 2: Attacks only on 1 core (label 1)
// Scenario 3: Benchmarks + Attacks on 2 cores (bench=label 2, attack=label 3)
// Scenario 4: Benchmarks on 2 cores (VM1+VM2), sequential (label 0)
// Scenario 5: Benchmarks on 2 cores (VM1+VM2), RANDOM (label 0)
// Scenario 6: RANDOM benchmarks (VM1+VM2) + Attacks (VM3)
// Scenario 7: RANDOM benchmarks (VM1+VM2) + Attacks with BENCHMARKS (VM3)
//             VM3 cycle: random_benchmark → Spectre → random_benchmark →
//             Armageddon → random_benchmark → Meltdown → repeat
// Scenario 8: FIXED benchmarks (VM1=SHA, VM2=FFT) + persistent Meltdown (VM3)
//             Core 1: SHA loop, Core 2: FFT loop, Core 3: Meltdown loop
// ===============================================
#define SCENARIO 9 // <-- CHANGE HERE TO SWITCH SCENARIO

#if SCENARIO == 1
// Solo benchmarks: VM0 (monitor) + VM1 (benchmarks)
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 0
#define EXEC_VM_3 0
#define SCENARIO_LABEL_BENCH 0
#define BENCHMARK_RANDOM 0
#define ACTIVE_IPC_CHANNELS 1 // VM1 only
#elif SCENARIO == 2
// Solo attacks: VM0 (monitor) + VM3 (Linux attacks)
#define EXEC_VM_0 1
#define EXEC_VM_1 0
#define EXEC_VM_2 0
#define EXEC_VM_3 1
#define SCENARIO_LABEL_ATTACK 1
#define BENCHMARK_RANDOM 0
#define ACTIVE_IPC_CHANNELS 1 // VM3 only
#elif SCENARIO == 3
// Benchmarks + attacks: VM0 + VM1 + VM3
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 0
#define EXEC_VM_3 1
#define SCENARIO_LABEL_BENCH 2
#define SCENARIO_LABEL_ATTACK 3
#define BENCHMARK_RANDOM 0
#define ACTIVE_IPC_CHANNELS 2 // VM1 + VM3
#elif SCENARIO == 4
// Benchmarks on 2 cores: VM0 (monitor) + VM1 (bench) + VM2 (bench)
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 1
#define EXEC_VM_3 0
#define SCENARIO_LABEL_BENCH 0
#define BENCHMARK_RANDOM 0
#define ACTIVE_IPC_CHANNELS 2 // VM1 + VM2
#elif SCENARIO == 5
// RANDOM benchmarks on 2 cores: VM0 (monitor) + VM1 + VM2 (random
// benchmarks)
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 1
#define EXEC_VM_3 0
#define SCENARIO_LABEL_BENCH 0
#define BENCHMARK_RANDOM 1
#define ACTIVE_IPC_CHANNELS 2 // VM1 + VM2
#elif SCENARIO == 6
// RANDOM benchmarks (VM1+VM2) + Attacks (VM3)
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 1
#define EXEC_VM_3 1
#define SCENARIO_LABEL_BENCH 2
#define SCENARIO_LABEL_ATTACK 3
#define BENCHMARK_RANDOM 1
#define ACTIVE_IPC_CHANNELS 3 // VM1 + VM2 + VM3
#elif SCENARIO == 7
// RANDOM benchmarks (VM1+VM2) + Attacks with random benchmarks on VM3
// VM3 cycle: random_benchmark → Spectre → random_benchmark → Armageddon →
// random_benchmark → Meltdown → repeat
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 1
#define EXEC_VM_3 1
#define SCENARIO_LABEL_BENCH 2
#define SCENARIO_LABEL_ATTACK 3
#define BENCHMARK_RANDOM 1
#define ACTIVE_IPC_CHANNELS 3 // VM1 + VM2 + VM3
#elif SCENARIO == 8
// FIXED benchmarks (VM1=SHA, VM2=FFT) + persistent Meltdown (VM3)
#define EXEC_VM_0 1
#define EXEC_VM_1 1
#define EXEC_VM_2 1
#define EXEC_VM_3 1
#define SCENARIO_LABEL_BENCH 2
#define SCENARIO_LABEL_ATTACK 3
#define BENCHMARK_RANDOM 0
#define BENCHMARK_FIXED 1
#define ACTIVE_IPC_CHANNELS 3 // VM1 + VM2 + VM3
#elif SCENARIO == 9
#define EXEC_VM_0 1
#define EXEC_VM_1 0
#define EXEC_VM_2 1
#define EXEC_VM_3 0
#define VM_2_IS_LINUX 1
#define SCENARIO_LABEL_BENCH 0
#define BENCHMARK_RANDOM 0
#define ACTIVE_IPC_CHANNELS 1
#else
#error "SCENARIO deve ser 1, 2, 3, 4, 5, 6, 7, 8 ou 9"
#endif

// Default BENCHMARK_FIXED for scenarios that don't define it
#ifndef BENCHMARK_FIXED
#define BENCHMARK_FIXED 0
#endif

#ifndef VM_2_IS_LINUX
#define VM_2_IS_LINUX 0
#endif

#define VM_QNT 4
#define TASK_QUANTITY 2

#define VM_0_REGULATION 1
#define VM_1_REGULATION 0
#define VM_2_REGULATION 0
#define VM_3_REGULATION 0

// Periodicity of each task
// #define PERIOD_MS_TASK_0 30
#define PERIOD_MS_TASK_PHONY 30
#define PERIOD_MS_TASK_ANY 30
#define PERIOD_MS_TASK_CTRL 10

// The time of the period for each task to run (old value 100)
// #define VM_0_PERIOD_REGULATION_MS_TASK_0 PERIOD_MS_TASK_0
// #define VM_0_PERIOD_REGULATION_MS_TASK_1 PERIOD_MS_TASK_1
//
// #define VM_1_PERIOD_REGULATION_MS_TASK_0 PERIOD_MS_TASK_0
// #define VM_1_PERIOD_REGULATION_MS_TASK_1 PERIOD_MS_TASK_1
//
// #define VM_2_PERIOD_REGULATION_MS_TASK_0 PERIOD_MS_TASK_0
// #define VM_2_PERIOD_REGULATION_MS_TASK_1 PERIOD_MS_TASK_1
//
// #define VM_3_PERIOD_REGULATION_MS_TASK_0 PERIOD_MS_TASK_0
// #define VM_3_PERIOD_REGULATION_MS_TASK_1 PERIOD_MS_TASK_1

// #define DEADLINE_MS_TASK_0 5
// #define DEADLINE_MS_TASK_1 10

// #define BENCHMARK_MAX_EXE 10
#define CACHE_COLORING 1

// =======================================
// Do not change below
// =======================================
#define INCREMENT_IF_EXEC_VM_0 (EXEC_VM_0 ? 1 : 0)
#define INCREMENT_IF_EXEC_VM_1 (EXEC_VM_1 ? 1 : 0)
#define INCREMENT_IF_EXEC_VM_2 (EXEC_VM_2 ? 1 : 0)
#define INCREMENT_IF_EXEC_VM_3 (EXEC_VM_3 ? 1 : 0)

#define RUNNING_VMs                                                            \
  (INCREMENT_IF_EXEC_VM_0 + INCREMENT_IF_EXEC_VM_1 + INCREMENT_IF_EXEC_VM_2 +  \
   INCREMENT_IF_EXEC_VM_3)

// #define BENCHMARK_QNT 8

struct VM {
  uint8_t pmu_counter_pair_rw;
  uint32_t r_fac;
  uint32_t w_fac;
  uint8_t sgi_suspend_task_budget;
  uint32_t total_read_allowed_budget;
  uint32_t total_write_allowed_budget;
  uint32_t new_read_budget;
  uint32_t new_write_budget;
  uint32_t deadline_met_counter;
  uint32_t deadline_missed_counter;
  uint32_t cycle_per_period[PERIOD_QNT];

  uint32_t period_start_time[PERIOD_QNT];
  uint32_t period_end_time[PERIOD_QNT];
  uint32_t task_deadline[PERIOD_QNT];
  uint32_t used_r_budget_period[PERIOD_QNT];
  uint32_t used_w_budget_period[PERIOD_QNT];
  uint32_t calc_r_budget_period[PERIOD_QNT];
  uint32_t calc_w_budget_period[PERIOD_QNT];

  uint32_t period_duration[PERIOD_QNT];
  uint32_t completed_runs_per_task[TASK_QUANTITY];
  uint32_t has_overflowed[PERIOD_QNT];
  //
  uint32_t PMU_raw_values[PMU_COUNT][PERIOD_QNT];
};

extern struct VM vm_conf[VM_QNT];

// typedef struct {
//   // uint8_t task_num;
//   uint8_t pmu_counter_a;
//   uint8_t pmu_counter_b;
//   uint8_t priority;
//   uint16_t periodicity;
//   uint8_t pmu_cpu_cycles_counter;
//   uint8_t show_exe_info;
//   uint32_t total_cpu_cycles;
//   uint32_t deadline_ms;
// } TASK;

// extern TASK task_conf[TASK_QNT];

// =======================================
// End of do-not-change section
// =======================================

#endif
