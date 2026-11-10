#ifndef TASKS_H
#define TASKS_H

// Entry point created by main(); starts the concurrent benchmark load
// (see bench_concurrent.h / bench_concurrent.c).
void task_orchestrator(void *arg);

#endif
