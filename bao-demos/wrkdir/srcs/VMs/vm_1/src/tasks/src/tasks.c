#include "../inc/tasks.h"
#include "FreeRTOS.h"
#include "task.h"
#include <stdio.h>

#include "../inc/globals.h"
#include "bench_concurrent.h"

// VM1 (FreeRTOS): background load for the pipeline scenario (SCENARIO 11).
//
// Instead of running one benchmark at a time, start the shared concurrent
// orchestrator (bench_concurrent), which keeps 2-3 distinct benchmarks running
// together and re-draws the set continuously. The same code runs on VM0 next to
// the PMU monitor.
void task_orchestrator(void *arg) {
  (void)arg;
  printf("[VM1] starting concurrent benchmark load (2-3 together)\n");
  fflush(stdout);
  bench_concurrent_start();
  vTaskDelete(NULL);
}
