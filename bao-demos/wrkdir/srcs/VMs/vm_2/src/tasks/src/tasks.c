#include "../inc/tasks.h"
#include "FreeRTOS.h"
#include "queue.h"
#include <stdio.h>

#include "../inc/globals.h"

#include "benchmarks_wrappers.h"
#include "regulation.h"

// Context for bandwidth benchmark
static bandwidth_context_fann_t bw_ctx;

void run_bandwidth(void) {
  bandwidth_wrapper_fann(&bw_ctx);
  asm volatile("" : : "r"(bw_ctx.sum) : "memory");
}

void run_disparity(void) { disparity_wrapper_fann(); }

void run_fft(void) { fft_wrapper_fann(); }

void run_qsort_bench(void) { qsort_wrapper_fann(); }

void run_dijkstra(void) { dijkstra_wrapper_fann(); }

void run_sha(void) { sha_wrapper_fann(); }

void run_sorting(void) { sorting_wrapper_fann(); }

void task_orchestrator(void *arg) {
  IPC_Channel *ipc = (IPC_Channel *)IPC_BASE_ADDR;

  bw_ctx.mem_ptr = (int *)pvPortMalloc(1024 * 1024);
  if (bw_ctx.mem_ptr == NULL) {
    printf("[VM2][ERROR] Not enough heap memory for Bandwidth!\n");
    vTaskDelete(NULL);
  }
  bw_ctx.sum = 0;

#if defined(BENCHMARK_NONE)
  // ============================================================
  // Phase 1: IDLE -- no benchmarks, no workload stress.
  // VM stays silent so VM0 can characterise clean PMU baselines.
  // ============================================================
  printf("[VM_2] BENCHMARK_NONE: idle (phase 1 - clean baseline).\n");
  fflush(stdout);
  ipc->current_label = LABEL_NONE;
  asm volatile("dsb sy" ::: "memory");
  while (1) {
    vTaskDelay(pdMS_TO_TICKS(1000));
  }

#elif BENCHMARK_FIXED
  // ============================================================
  // Scenario 8: FIXED — VM2 runs FFT in infinite loop
  // ============================================================
  printf("[VM2] Orchestrator Task (FIXED: FFT) started. IPC channel: 0x%x\n", IPC_BASE_ADDR);
  fflush(stdout);

  g_label_atual = (float)LABEL_FFT;
  ipc->current_label = LABEL_FFT;
  asm volatile("dsb sy" ::: "memory");

  TickType_t next_sync = xTaskGetTickCount() + pdMS_TO_TICKS(SYNC_INTERVAL_MS);

  while (1) {
    run_fft();

    if (xTaskGetTickCount() >= next_sync) {
      ipc->current_label = LABEL_FFT;
      asm volatile("dsb sy" ::: "memory");

      ipc->signal_ready = 1;

      while (ipc->resume == 0) {
        vTaskDelay(pdMS_TO_TICKS(1));
      }

      ipc->resume = 0;
      asm volatile("dsb sy" ::: "memory");

      next_sync = xTaskGetTickCount() + pdMS_TO_TICKS(SYNC_INTERVAL_MS);
    }
  }

#elif BENCHMARK_RANDOM
  prng_seed_from_timer();

  printf("[VM2] Orchestrator Task (RANDOM) started. IPC channel: 0x%x\n",
         IPC_BASE_ADDR);
  fflush(stdout);

  TickType_t next_sync = xTaskGetTickCount() + pdMS_TO_TICKS(SYNC_INTERVAL_MS);

  while (1) {
    int bench = (int)prng_range(LABEL_BANDWIDTH, NUM_BENCHMARKS);

    g_label_atual = (float)bench;
    ipc->current_label = bench;
    asm volatile("dsb sy" ::: "memory");

    switch (bench) {
    case LABEL_BANDWIDTH:
      run_bandwidth();
      break;
    case LABEL_DISPARITY:
      run_disparity();
      break;
    case LABEL_FFT:
      run_fft();
      break;
    case LABEL_QSORT:
      run_qsort_bench();
      break;
    case LABEL_DIJKSTRA:
      run_dijkstra();
      break;
    case LABEL_SHA:
      run_sha();
      break;
    case LABEL_SORTING:
      run_sorting();
      break;
    }

    if (xTaskGetTickCount() >= next_sync) {
      ipc->current_label = bench;
      asm volatile("dsb sy" ::: "memory");

      ipc->signal_ready = 1;

      while (ipc->resume == 0) {
        vTaskDelay(pdMS_TO_TICKS(1));
      }

      ipc->resume = 0;
      asm volatile("dsb sy" ::: "memory");

      next_sync = xTaskGetTickCount() + pdMS_TO_TICKS(SYNC_INTERVAL_MS);
    }
  }

#else
  // VM2 runs benchmarks in REVERSE order: Sorting (7) -> Bandwidth (1)
  int current_bench = LABEL_SORTING;

  printf("[VM2] Orchestrator Task started. IPC channel: 0x%x\n", IPC_BASE_ADDR);
  fflush(stdout);

  while (1) {
    TickType_t start_time = xTaskGetTickCount();
    TickType_t next_sync = start_time + pdMS_TO_TICKS(SYNC_INTERVAL_MS);
    TickType_t end_time = start_time + pdMS_TO_TICKS(BENCHMARK_DURATION_MS);

    g_label_atual = (float)current_bench;
    ipc->current_label = current_bench;
    asm volatile("dsb sy" ::: "memory");
    printf("[VM2] Running benchmark %d (reverse order) for 10 minutes...\n", current_bench);
    fflush(stdout);

    while (xTaskGetTickCount() < end_time) {
      switch (current_bench) {
      case LABEL_BANDWIDTH:
        run_bandwidth();
        break;
      case LABEL_DISPARITY:
        run_disparity();
        break;
      case LABEL_FFT:
        run_fft();
        break;
      case LABEL_QSORT:
        run_qsort_bench();
        break;
      case LABEL_DIJKSTRA:
        run_dijkstra();
        break;
      case LABEL_SHA:
        run_sha();
        break;
      case LABEL_SORTING:
        run_sorting();
        break;
      }

      if (xTaskGetTickCount() >= next_sync) {
        ipc->current_label = current_bench;
        asm volatile("dsb sy" ::: "memory");

        ipc->signal_ready = 1;

        while (ipc->resume == 0) {
          vTaskDelay(pdMS_TO_TICKS(1));
        }

        ipc->resume = 0;
        asm volatile("dsb sy" ::: "memory");

        next_sync = xTaskGetTickCount() + pdMS_TO_TICKS(SYNC_INTERVAL_MS);
      }
    }

    current_bench--;
    if (current_bench < LABEL_BANDWIDTH) {
      current_bench = LABEL_SORTING;
    }
  }
#endif
}
