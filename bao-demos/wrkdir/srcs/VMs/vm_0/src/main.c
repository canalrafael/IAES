/*
 * FreeRTOS Kernel V10.2.1
 * Copyright (C) 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * http://www.FreeRTOS.org
 * http://aws.amazon.com/freertos
 *
 * 1 tab == 4 spaces!
 */

/* FreeRTOS kernel includes. */
#include <stdio.h>
#include <sys/time.h>

#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#include "tasks_project.h"
#include "globals.h"
extern void task_inference(void *arg);

QueueHandle_t xPmuQueue = NULL;
volatile float g_label_atual = 0.0f;

int _gettimeofday(struct timeval *tv, void *tz) {
    if (tv) {
        tv->tv_sec = 0;
        tv->tv_usec = 0;
    }
    return 0;
}

int _open(const char *name, int flags, int mode) { return -1; }

// void _init(void) {}
void _fini(void) {}

int main(void) {

  // Create queue for PMU -> FANN communication
  xPmuQueue = xQueueCreate(100, sizeof(FANN_sample));
  if(xPmuQueue == NULL) {
      printf("Error: queue not created\n");
      while(1);
  }
  printf("Queue created successfully\n");
  xTaskCreate(
    task_monitor,
    "taskMonitor",
    TASK_STACK_SIZE,
    NULL,
    OTHER_TASK_PRIORITY,
    NULL
  );

  
  xTaskCreate(
    task_inference,
    "taskInference",
    TASK_STACK_SIZE,
    NULL,
    OTHER_TASK_PRIORITY,
    NULL
  );

  vTaskStartScheduler();
  while (1) {
    //
  }
  // printf("\nReturning from main.\n");
  return 0;
}

/*-----------------------------------------------------------*/
void vApplicationDaemonTaskStartupHook(void) {
  printf("vApplicationDaemonTaskStartupHook(void)\n");
}

void vApplicationMallocFailedHook(void) {
  /* vApplicationMallocFailedHook() will only be called if
         configUSE_MALLOC_FAILED_HOOK is set to 1 in FreeRTOSConfig.h.  It is a
     hook function that will get called if a call to pvPortMalloc() fails.
         pvPortMalloc() is called internally by the kernel whenever a task,
     queue, timer or semaphore is created.  It is also called by various parts
     of the demo application.  If heap_1.c or heap_2.c are used, then the size
     of the heap available to pvPortMalloc() is defined by configTOTAL_HEAP_SIZE
     in FreeRTOSConfig.h, and the xPortGetFreeHeapSize() API function can be
     used to query the size of free heap space that remains (although it does
     not provide information on how the remaining heap might be fragmented). */
  printf("vApplicationMallocFailedHook(void)\n");
  taskDISABLE_INTERRUPTS();
  for (;;)
    ;
}

void vApplicationIdleHook(void) {
  /* vApplicationIdleHook() will only be called if configUSE_IDLE_HOOK is set
         to 1 in FreeRTOSConfig.h.  It will be called on each iteration of the
     idle task.  It is essential that code added to this hook function never
     attempts to block in any way (for example, call xQue     ueReceive() with a
     block time specified, or call vTaskDelay()).  If the application makes use
     of the vTaskDelete() API function (as this demo application does) then it
     is also important that vApplicationIdleHook() is permitted to return to its
     calling function, because it is the responsibility of the idle task to
     clean up memory allocated by the kernel to any task that has since been
     deleted. */

  printf("void vApplicationIdleHook(void)\n");
}

void vApplicationStackOverflowHook(TaskHandle_t pxTask, char *pcTaskName) {
  (void)pcTaskName;
  (void)pxTask;

  /* Run time stack overflow checking is performed if
         configCHECK_FOR_STACK_OVERFLOW is defined to 1 or 2.  This hook
         function is called if a stack overflow is detected. */
  printf(
      "vApplicationStackOverflowHook(TaskHandle_t pxTask, char *pcTaskName)\n");
  taskDISABLE_INTERRUPTS();
  for (;;)
    ;
}

void vApplicationTickHook(void) {
  printf("vApplicationTickHook(void)\n");
  for (;;)
    ;
}

void vAssertCalled(void) {
  printf("vAssertCalled(void)\n");
  volatile uint32_t ulSetTo1ToExitFunction = 0;

  taskDISABLE_INTERRUPTS();
  while (ulSetTo1ToExitFunction != 1) {
    __asm volatile("NOP");
  }
}

/* This version of vApplicationAssert() is declared as a weak symbol to allow it
   to be overridden by a version implemented within the application that is
   using this BSP. */
void vApplicationAssert(const char *pcFileName, uint32_t ulLine) {
  printf("vApplicationAssert( const char *pcFileName, uint32_t ulLine )\n");
  volatile uint32_t ul = 0;
  volatile const char *pcLocalFileName =
      pcFileName; /* To prevent pcFileName being optimized away. */
  volatile uint32_t ulLocalLine =
      ulLine; /* To prevent ulLine being optimized away. */

  /* Prevent compile warnings about the following two variables being set but
     not referenced.  They are intended for viewing in the debugger. */
  (void)pcLocalFileName;
  (void)ulLocalLine;

  printf("Assert failed in file %s, line %lu\r\n", pcLocalFileName,
         ulLocalLine);

  /* If this function is entered then a call to configASSERT() failed in the
     FreeRTOS code because of a fatal error.  The pcFileName and ulLine
     parameters hold the file name and line number in that file of the assert
     that failed.  Additionally, if using the debugger, the function call stack
     can be viewed to find which line failed its configASSERT() test.  Finally,
     the debugger can be used to set ul to a non-zero value, then step out of
     this function to find where the assert function was entered. */
  taskENTER_CRITICAL();
  {
    while (ul == 0) {
      __asm volatile("NOP");
    }
  }
  taskEXIT_CRITICAL();
}