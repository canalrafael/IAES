# Prepare enviroment for baremetal-runtime
NAME:=vm_0
ROOT_DIR:=$(realpath .)
BUILD_DIR:=$(ROOT_DIR)/build/$(PLATFORM)

# Setup baremetal-runtime build
bmrt_dir:=$(ROOT_DIR)/src/baremetal-runtime
include $(bmrt_dir)/setup.mk

#BAO_DEMOS_WRKDIR_SRC=$(ROOT_DIR)/../..

# Include all freertos sources
INC_GUEST_COMMON=$(BAO_DEMOS_WRKDIR_SRC)/guest_common/inc
SRC_GUEST_COMMON=$(BAO_DEMOS_WRKDIR_SRC)/guest_common/src

# Main freertos application sources
app_src_dir:=$(ROOT_DIR)/src
include $(app_src_dir)/sources.mk
C_SRC+=$(addprefix $(app_src_dir)/, $(src_c_srcs))


# Freertos kernel sources
freertos_dir:=$(ROOT_DIR)/src/freertos
SRC_DIRS+=$(freertos_dir) $(freertos_memmng_dir)
INC_DIRS+=$(freertos_dir)/include
C_SRC+=$(wildcard $(freertos_dir)/*.c)
freertos_memmng_dir:=$(freertos_dir)/portable/MemMang
C_SRC+=$(freertos_memmng_dir)/heap_4.c

# Freertos port arch-specific (here the compiler discovers the RPi4 portmacro.h)
arch_dir=$(ROOT_DIR)/src/arch/$(ARCH)
SRC_DIRS+=$(arch_dir)
INC_DIRS+=$(arch_dir)/inc
-include $(arch_dir)/arch.mk
-include $(arch_dir)/sources.mk
C_SRC+=$(addprefix $(arch_dir)/, $(arch_c_srcs))
ASM_SRC+=$(addprefix $(arch_dir)/, $(arch_s_srcs))

#fann
FANN_ROOT = $(BAO_DEMOS_WRKDIR_SRC)/fann
FANN_SRC  = $(FANN_ROOT)/src
FANN_INC  = $(FANN_ROOT)/src/include

INC_DIRS += $(FANN_INC)
C_SRC += $(FANN_SRC)/floatfann.c

LD_LIBS += -lm
CFLAGS+= -Os -ffunction-sections -fdata-sections

#injecao de tempo real
EPOCH_TIME := $(shell date +%s)
CFLAGS += -DBUILD_EPOCH=$(EPOCH_TIME)

#neural network
INC_NEURAL_NETWORK=$(BAO_DEMOS_WRKDIR_SRC)/neural_network/inc
SRC_NEURAL_NETWORK=$(BAO_DEMOS_WRKDIR_SRC)/neural_network/src
INC_DIRS += $(INC_NEURAL_NETWORK)
C_SRC+=$(wildcard $(SRC_NEURAL_NETWORK)/*.c)

#pmu monitor
INC_PMU_MONITOR=$(BAO_DEMOS_WRKDIR_SRC)/pmu_monitor/inc
SRC_PMU_MONITOR=$(BAO_DEMOS_WRKDIR_SRC)/pmu_monitor/src
INC_DIRS += $(INC_PMU_MONITOR)
C_SRC+=$(wildcard $(SRC_PMU_MONITOR)/*.c)

# OTHERS SRCS
C_SRC+=$(wildcard $(SRC_GUEST_COMMON)/*.c)

# OTHERS INCLUDES
INC_DIRS+=$(INC_GUEST_COMMON)


# Neurosurgeon
INC_NEUROSURGEON=$(BAO_DEMOS_WRKDIR_SRC)/neurosurgeon/inc
SRC_NEUROSURGEON=$(BAO_DEMOS_WRKDIR_SRC)/neurosurgeon/src
INC_DIRS += $(INC_NEUROSURGEON)
C_SRC+=$(wildcard $(SRC_NEUROSURGEON)/*.c)

#TASKS

INC_TASKS=$(BAO_DEMOS_WRKDIR_SRC)/VMs/vm_0/src/tasks/inc
SRC_TASKS=$(BAO_DEMOS_WRKDIR_SRC)/VMs/vm_0/src/tasks/src
INC_DIRS += $(INC_TASKS)
C_SRC+=$(wildcard $(SRC_TASKS)/*.c)

LDFLAGS += $(CFLAGS)

# Include the final baremetal-runtime build
include $(bmrt_dir)/build.mk