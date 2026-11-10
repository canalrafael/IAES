#include "../../../../srcs/guest_common/inc/regulation.h"
#include <config.h>

VM_IMAGE(vm_0_img, XSTR(BAO_DEMOS_WRKDIR_IMGS/vm_0.bin));
#if EXEC_VM_1
VM_IMAGE(vm_1_img, XSTR(BAO_DEMOS_WRKDIR_IMGS/vm_1.bin));
#endif
#if EXEC_VM_2
VM_IMAGE(vm_2_img, XSTR(BAO_DEMOS_WRKDIR_IMGS/vm_2.bin));
#endif
#if EXEC_VM_3
VM_IMAGE(vm_3_img, XSTR(BAO_DEMOS_WRKDIR_IMGS/vm_3.bin));
#endif

// Active scenario: SCENARIO (defined in regulation.h)

struct config config =
    {
        CONFIG_HEADER

            .shmemlist_size = ACTIVE_IPC_CHANNELS,
        .shmemlist = (struct shmem[]){
#if EXEC_VM_1
            [0] = { .size = 0x00010000 },  // Channel 0: VM0 <-> VM1
#endif
#if EXEC_VM_2 && EXEC_VM_1
            [1] = { .size = 0x00010000 },  // Channel 1: VM0 <-> VM2
#endif
#if EXEC_VM_3 && EXEC_VM_2 && EXEC_VM_1 && !VM_2_IS_LINUX
            [2] = { .size = 0x00010000 },  // Channel 2: VM0 <-> VM3 (scenario 6)
#elif EXEC_VM_3 && EXEC_VM_1 && !VM_2_IS_LINUX
            [1] = { .size = 0x00010000 },  // Channel 1: VM0 <-> VM3 (scenario 3)
#elif EXEC_VM_3 && !VM_2_IS_LINUX
            [0] = { .size = 0x00010000 },  // Channel 0: VM0 <-> VM3 (scenario 2)
#endif
            // VM_2_IS_LINUX (scenarios 9/10/11): VM3 has no IPC channel.
#if !EXEC_VM_1 && EXEC_VM_2 && !EXEC_VM_3
            [0] = { .size = 0x00010000 },  // Channel 0: VM0 <-> VM2 (scenario 9)
#endif
        },

        .vmlist_size = RUNNING_VMs,
        .vmlist =
            {

#if EXEC_VM_0
                // -------------------
                // CORE 0 - BEGINNING
                // -------------------
                {
                    .image = {.base_addr = 0x0,

                              .load_addr = VM_IMAGE_OFFSET(vm_0_img),
                              .size = VM_IMAGE_SIZE(vm_0_img)},

                    .entry = 0x0,
#if CACHE_COLORING
                    .colors = 0b1,
#else
                    .colors = 0b0,
#endif
                    .cpu_affinity = 0b1,

                    .platform = {.cpu_num = 1,

                                 .region_num = 1,
                                 .regions =
                                     (struct vm_mem_region[]){
                                         {.base = 0x0, .size = 0x4000000}},

                                 .ipc_num = ACTIVE_IPC_CHANNELS,
                                 .ipcs = (struct ipc[]){
#if EXEC_VM_1
                                     {.base = 0x70000000, .size = 0x00010000, .shmem_id = 0,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){52}},
#endif
#if EXEC_VM_2 && EXEC_VM_1
                                     {.base = 0x70020000, .size = 0x00010000, .shmem_id = 1,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){53}},
#endif
#if EXEC_VM_3 && EXEC_VM_2 && EXEC_VM_1 && !VM_2_IS_LINUX
                                     {.base = 0x70040000, .size = 0x00010000, .shmem_id = 2,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){54}},
#elif EXEC_VM_3 && EXEC_VM_1 && !VM_2_IS_LINUX
                                     {.base = 0x70020000, .size = 0x00010000, .shmem_id = 1,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){53}},
#elif EXEC_VM_3 && !VM_2_IS_LINUX
                                     {.base = 0x70020000, .size = 0x00010000, .shmem_id = 0,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){52}},
#endif
                                     // VM_2_IS_LINUX (scn 9/10/11): no VM0<->VM3 channel.
#if !EXEC_VM_1 && EXEC_VM_2 && !EXEC_VM_3
                                     {.base = 0x70020000, .size = 0x00010000, .shmem_id = 0,
                                      .interrupt_num = 1, .interrupts = (irqid_t[]){52}},
#endif
                                 },

                                 .dev_num = 2,
                                 .devs =
                                     (struct vm_dev_region[]){
                                          {/* UART1 - mini-UART (GPIO 14/15) */
                                          .pa = 0xfe215000,
                                          .va = 0xff000000,
                                          .size = 0x1000,
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){125}},
                                         {/* Arch timer interrupt */
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){27}},
                                     },
                                 .arch = {.gic =
                                              {
                                                  .gicd_addr = 0xF9010000,
                                                  .gicc_addr = 0xF9020000,
                                              }}},
                },

// ------------
// CORE 0 - END
// ------------
#endif

#if EXEC_VM_1
                // -------------------
                // CORE 1 - BEGINNING
                // -------------------
                {
                    .image = {.base_addr = 0x0,

                              .load_addr = VM_IMAGE_OFFSET(vm_1_img),
                              .size = VM_IMAGE_SIZE(vm_1_img)},

                    .entry = 0x0,
#if CACHE_COLORING
                    .colors = 0b10,
#else
                    .colors = 0b0,
#endif
                    .cpu_affinity = 0b10,

                    .platform = {.cpu_num = 1,

                                 .region_num = 1,
                                 .regions =
                                     (struct vm_mem_region[]){
                                         {.base = 0x0, .size = 0x4000000}},

                                 .ipc_num = 1,
                                 .ipcs = (struct ipc[]){{.base = 0x70000000,
                                                         .size = 0x00010000,
                                                         .shmem_id = 0,
                                                         .interrupt_num = 1,
                                                         .interrupts =
                                                             (irqid_t[]){52}}},

                                 .dev_num = 2,
                                 .devs =
                                     (struct vm_dev_region[]){
                                         {/* UART1 */
                                          .pa = 0xfe215000,
                                          .va = 0xff000000,
                                          .size = 0x1000,
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){126}},
                                         {/* Arch timer interrupt */
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){27}},
                                     },
                                 .arch = {.gic =
                                              {
                                                  .gicd_addr = 0xF9010000,
                                                  .gicc_addr = 0xF9020000,
                                              }}},
                },
// ------------
// CORE 1 - END
// ------------
#endif

#if EXEC_VM_2
                // -------------------
                // CORE 2 - BEGINNING
                // -------------------
#if VM_2_IS_LINUX
                {
                    .image = {.base_addr = 0x0,

                              .load_addr = VM_IMAGE_OFFSET(vm_2_img),
                              .size = VM_IMAGE_SIZE(vm_2_img)},

                    .entry = 0x0,
#if CACHE_COLORING
                    .colors = 0b100,  // single color: lean Linux fits in ~989MB/color
#else
                    .colors = 0b0,
#endif
                    .cpu_affinity = 0b100,

                    .platform = {.cpu_num = 1,

                                 .region_num = 1,
                                 .regions =
                                     (struct vm_mem_region[]){
                                         {.base = 0x0, .size = 0x10000000}},  // 256 MB

                                 .ipc_num = 1,
                                 .ipcs = (struct ipc[]){{.base = 0x70000000,
                                                         .size = 0x00010000,
#if EXEC_VM_1
                                                         .shmem_id = 1,  // scn 11: VM0<->VM2 is channel 1
#else
                                                         .shmem_id = 0,  // scn 9/10: only channel
#endif
                                                         .interrupt_num = 1,
                                                         .interrupts =
                                                             (irqid_t[]){52}}},

                                 .dev_num = 4,
                                 .devs =
                                     (struct vm_dev_region[]){
                                         {/* GPIO para Pin Muxing. Aligned to 4KB! */
                                          .pa = 0xfe200000,
                                          .va = 0xfe200000,
                                          .size = 0x1000},
                                         {/* UART4 (PL011) console para o Linux. Aligned to 4KB! */
                                          .pa = 0xfe201000,
                                          .va = 0xfe201000,
                                          .size = 0x2000,
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){128}},
                                         {/* UART1 (mini-UART) para DEBUG. Aligned to 4KB! */
                                          .pa = 0xfe215000,
                                          .va = 0xfe215000,
                                          .size = 0x1000},
                                         {/* Arch timer interrupt */
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){27}},
                                     },
                                 .arch = {.gic =
                                              {
                                                  .gicd_addr = 0xF9010000,
                                                  .gicc_addr = 0xF9020000,
                                              }}},
                },
#else
                {
                    .image = {.base_addr = 0x0,

                              .load_addr = VM_IMAGE_OFFSET(vm_2_img),
                              .size = VM_IMAGE_SIZE(vm_2_img)},

                    .entry = 0x0,
#if CACHE_COLORING
                    .colors = 0b100,
#else
                    .colors = 0b0,
#endif
                    .cpu_affinity = 0b100,

                    .platform = {.cpu_num = 1,

                                 .region_num = 1,
                                 .regions =
                                     (struct vm_mem_region[]){
                                         {.base = 0x0, .size = 0x4000000}},

                                 .ipc_num = 1,
                                 .ipcs = (struct ipc[]){{.base = 0x70000000,
                                                         .size = 0x00010000,
                                                         .shmem_id = 1,
                                                         .interrupt_num = 1,
                                                         .interrupts =
                                                             (irqid_t[]){52}}},

                                 .dev_num = 2,
                                 .devs =
                                     (struct vm_dev_region[]){
                                         {/* UART1 */
                                          .pa = 0xfe215000,
                                          .va = 0xff000000,
                                          .size = 0x1000,
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){127}},
                                         {/* Arch timer interrupt */
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){27}},
                                     },
                                 .arch = {.gic =
                                              {
                                                  .gicd_addr = 0xF9010000,
                                                  .gicc_addr = 0xF9020000,
                                              }}},
                },
#endif // VM_2_IS_LINUX
// ------------
// CORE 2 - END
// ------------
#endif

#if EXEC_VM_3
                // -------------------
                // CORE 3 - BEGINNING
                // -------------------
                {
                    .image = {.base_addr = 0x0,

                              .load_addr = VM_IMAGE_OFFSET(vm_3_img),
                              .size = VM_IMAGE_SIZE(vm_3_img)},

                    .entry = 0x0,
#if CACHE_COLORING
                    .colors = 0b1000,
#else
                    .colors = 0b0,
#endif
                    .cpu_affinity = 0b1000,

                    .platform = {.cpu_num = 1,

                                 .region_num = 1,
                                 .regions =
                                     (struct vm_mem_region[]){
                                         {.base = 0x0, .size = 0x10000000}},

#if VM_2_IS_LINUX && EXEC_VM_3
                                 // scenarios 10/11: VM2 is the Linux peer of the
                                 // monitor; VM3 (contention / attacks) has no IPC
                                 // channel and the monitor ignores it.
                                 .ipc_num = 0,
#else
                                 .ipc_num = 1,
#endif
                                 .ipcs = (struct ipc[]){{.base = 0x70000000,
                                                         .size = 0x00010000,
#if EXEC_VM_2 && EXEC_VM_1
                                                         .shmem_id = 2,  // scenario 6: VM3 uses channel 2
#elif EXEC_VM_1
                                                         .shmem_id = 1,  // scenario 3: VM3 uses channel 1
#else
                                                         .shmem_id = 0,  // scenario 2: VM3 uses channel 0
#endif
                                                         .interrupt_num = 1,
                                                         .interrupts =
                                                             (irqid_t[]){52}}},

                                 .dev_num = 4,
                                 .devs =
                                     (struct vm_dev_region[]){
                                         {/* GPIO para Pin Muxing. Aligned to 4KB! */
                                          .pa = 0xfe200000,
                                          .va = 0xfe200000,
                                          .size = 0x1000},
                                         {/* UART4 para o linux (GPIO 8/9). Aligned to 4KB! */
                                          .pa = 0xfe201000,
                                          .va = 0xfe201000,
                                          .size = 0x2000,
#if VM_2_IS_LINUX && EXEC_VM_3
                                          // scenarios 10/11: VM2 owns the uart4 IRQ (128).
                                          // VM3 maps the UART for polled TX only (no IRQ),
                                          // so the GIC interrupt is not claimed twice.
                                          .interrupt_num = 0},
#else
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){128}},
#endif
                                         {/* UART1 (FreeRTOS) para DEBUG do Linux. Aligned to 4KB! */
                                          .pa = 0xfe215000,
                                          .va = 0xfe215000,
                                          .size = 0x1000},
                                         {/* Arch timer interrupt */
                                          .interrupt_num = 1,
                                          .interrupts = (irqid_t[]){27}},
                                     },
                                 .arch = {.gic =
                                              {
                                                  .gicd_addr = 0xF9010000,
                                                  .gicc_addr = 0xF9020000,
                                              }}},
                },
// ------------
// CORE 3 - END
// ------------
#endif

            },
};
