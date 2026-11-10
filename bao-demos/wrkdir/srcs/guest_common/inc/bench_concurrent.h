#ifndef BENCH_CONCURRENT_H
#define BENCH_CONCURRENT_H

// Background benchmark load for the "pipeline" scenario (SCENARIO 11).
//
// Starts a small set of FreeRTOS worker tasks plus one orchestrator task. The
// orchestrator continuously draws 2 or 3 DISTINCT benchmarks and assigns them to
// the workers, so 2-3 benchmarks run together (time-sliced on this core), and
// re-draws the set every window, without ever stopping.
//
// Call once from main() (before vTaskStartScheduler) or from a startup task.
// The worker/orchestrator tasks run at a low priority so a higher-priority task
// (e.g. VM0's PMU monitor) keeps its cadence.
void bench_concurrent_start(void);

#endif // BENCH_CONCURRENT_H
