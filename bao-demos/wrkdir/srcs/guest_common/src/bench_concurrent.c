#include "bench_concurrent.h"

#include <stddef.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "task.h"

#include "benchmarks_wrappers.h"

// Shared bandwidth buffer, defined in benchmarks_wrappers.c (NUM_INTS ints).
// Only one worker runs the bandwidth benchmark at a time (the set is always
// distinct), so a single shared buffer is safe and avoids any heap allocation.
extern int g_bw_memory[];

#define BENCH_WORKERS      3       // up to 3 benchmarks at once
#define BENCH_WINDOW_MS    15000   // re-draw the active set every 15 s
#define BENCH_WORKER_PRIO  1       // below the PMU monitor (higher) on VM0
#define BENCH_ORCH_PRIO    1
#define BENCH_WORKER_STACK 4096    // words; qsort/disparity need room
#define BENCH_ORCH_STACK   1024

// Benchmark ids match globals.h LABEL_* (1..7). 0 means "idle".
#define BENCH_FIRST 1
#define BENCH_LAST  7

static volatile int g_worker_bench[BENCH_WORKERS];

// Small LCG seeded from the cycle counter (no stdlib dependency).
static uint32_t rng_state;
static void rng_seed(void) {
  uint64_t v;
  asm volatile("isb\n mrs %0, cntvct_el0" : "=r"(v));
  rng_state = (uint32_t)(v ^ (v >> 32));
  if (rng_state == 0) rng_state = 1;
}
static uint32_t rng_next(void) {
  rng_state = rng_state * 1664525u + 1013904223u;
  return rng_state;
}
// inclusive range [lo, hi]
static uint32_t rng_range(uint32_t lo, uint32_t hi) {
  return lo + (rng_next() % (hi - lo + 1));
}

static void run_one(int id, bandwidth_context_fann_t *bw) {
  switch (id) {
    case 1: bw->mem_ptr = g_bw_memory; bandwidth_wrapper_fann(bw); break;
    case 2: disparity_wrapper_fann(); break;
    case 3: fft_wrapper_fann();       break;
    case 4: qsort_wrapper_fann();     break;
    case 5: dijkstra_wrapper_fann();  break;
    case 6: sha_wrapper_fann();       break;
    case 7: sorting_wrapper_fann();   break;
    default: vTaskDelay(pdMS_TO_TICKS(5)); break;
  }
}

static void worker_task(void *arg) {
  int idx = (int)(intptr_t)arg;
  bandwidth_context_fann_t bw = { .mem_ptr = g_bw_memory, .sum = 0 };
  for (;;) {
    int id = g_worker_bench[idx];
    if (id == 0) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    run_one(id, &bw);
    asm volatile("" ::: "memory");
  }
}

static void orchestrator_task(void *arg) {
  (void)arg;
  rng_seed();
  for (;;) {
    int k = (int)rng_range(2, 3);           // 2 or 3 together
    if (k > BENCH_WORKERS) k = BENCH_WORKERS;

    int chosen[BENCH_WORKERS];
    int n = 0;
    while (n < k) {
      int cand = (int)rng_range(BENCH_FIRST, BENCH_LAST);
      int dup = 0;
      for (int i = 0; i < n; i++)
        if (chosen[i] == cand) dup = 1;
      if (!dup) chosen[n++] = cand;
    }

    for (int i = 0; i < BENCH_WORKERS; i++)
      g_worker_bench[i] = (i < k) ? chosen[i] : 0;

    vTaskDelay(pdMS_TO_TICKS(BENCH_WINDOW_MS));
  }
}

void bench_concurrent_start(void) {
  for (int i = 0; i < BENCH_WORKERS; i++)
    g_worker_bench[i] = 0;

  for (int i = 0; i < BENCH_WORKERS; i++)
    xTaskCreate(worker_task, "bench_w", BENCH_WORKER_STACK,
                (void *)(intptr_t)i, BENCH_WORKER_PRIO, NULL);

  xTaskCreate(orchestrator_task, "bench_orch", BENCH_ORCH_STACK,
              NULL, BENCH_ORCH_PRIO, NULL);
}
