NAME:=vm_3
ROOT_DIR:=$(realpath .)

.DEFAULT_GOAL := all

wrkdir_demo_imgs := $(ROOT_DIR)/build/$(PLATFORM)
TARGET := $(wrkdir_demo_imgs)/$(NAME).bin

wrkdir_src := $(ROOT_DIR)
bao_demos ?= $(BAO_DEMOS)

include $(BAO_DEMOS)/guests/linux/make.mk

BUILDROOT_DIR := $(buildroot_src)
CC_ARM := $(BUILDROOT_DIR)/output/host/bin/aarch64-buildroot-linux-uclibc-gcc
CUSTOM_OVERLAY := $(wrkdir_src)/custom_overlay
OVERLAY_DIR := $(CUSTOM_OVERLAY)/root

SPECTRE_SRC := $(wrkdir_src)/attacks/spectre/src/spectre_attack.c
ARMAGEDDON_SRC := $(wrkdir_src)/attacks/armageddon/src/armageddon.c
MELTDOWN_SRC := $(wrkdir_src)/attacks/meltdown/src/meltdown.c
ZOMBIELOAD_SRC := $(wrkdir_src)/attacks/zombieload/src/zombieload.c

# --- Benchmark sources (for scenario 7: benchmarks on core 3) ---
BENCH_ROOT := $(ROOT_DIR)/../../benchmarks
BENCH_MAIN_SRC := $(OVERLAY_DIR)/main_benchmark.c
BENCH_WRAPPER_SRC := $(BENCH_ROOT)/wrappers/src/benchmarks_wrappers.c
BENCH_C_SRCS := $(BENCH_ROOT)/bandwidth/src/bandwidth.c \
                $(BENCH_ROOT)/dijkstra/src/dijkstra.c \
                $(BENCH_ROOT)/disparity/src/computeSAD.c \
                $(BENCH_ROOT)/disparity/src/correlateSAD_2D.c \
                $(BENCH_ROOT)/disparity/src/disparity.c \
                $(BENCH_ROOT)/disparity/src/finalSAD.c \
                $(BENCH_ROOT)/disparity/src/findDisparity.c \
                $(BENCH_ROOT)/disparity/src/getDisparity.c \
                $(BENCH_ROOT)/disparity/src/integralImage2D2D.c \
                $(BENCH_ROOT)/disparity/src/padarray2.c \
                $(BENCH_ROOT)/disparity/src/padarray4.c \
                $(BENCH_ROOT)/fft/src/driver.c \
                $(BENCH_ROOT)/fft/src/fft.c \
                $(BENCH_ROOT)/mser/src/mser.c \
                $(BENCH_ROOT)/qsort/src/qsort.c \
                $(BENCH_ROOT)/sha/src/sha.c \
                $(BENCH_ROOT)/sha/src/sha_driver.c \
                $(BENCH_ROOT)/sorting/src/sorting.c

BENCH_INC_DIRS := -I$(BENCH_ROOT)/wrappers/inc \
                  -I$(BENCH_ROOT)/bandwidth/inc \
                  -I$(BENCH_ROOT)/dijkstra/inc \
                  -I$(BENCH_ROOT)/disparity/inc \
                  -I$(BENCH_ROOT)/fft/inc \
                  -I$(BENCH_ROOT)/mser/inc \
                  -I$(BENCH_ROOT)/qsort/inc \
                  -I$(BENCH_ROOT)/sha/inc \
                  -I$(BENCH_ROOT)/sorting/inc

CUSTOM_APPS := $(OVERLAY_DIR)/spectre \
               $(OVERLAY_DIR)/armageddon \
               $(OVERLAY_DIR)/meltdown \
               $(OVERLAY_DIR)/zombieload \
               $(OVERLAY_DIR)/benchmark \
               $(OVERLAY_DIR)/ipc_signal \
               $(OVERLAY_DIR)/ipc_sync \
               $(OVERLAY_DIR)/memhog

$(OVERLAY_DIR)/memhog: $(OVERLAY_DIR)/memhog.c | $(CC_ARM)
	@echo ">> Compiling memhog (memory-bandwidth contention)..."
	$(CC_ARM) -O2 $< -o $@


$(BUILDROOT_DIR)/output/host/bin/aarch64-buildroot-linux-uclibc-gcc: | $(BUILDROOT_DIR) $(linux_src)
	@echo ">> Buildroot toolchain not found. Building buildroot (this may take a while)..."
	$(MAKE) -C $(BUILDROOT_DIR) defconfig BR2_DEFCONFIG=$(buildroot_defcfg)
	$(MAKE) -C $(BUILDROOT_DIR)

# --- Attack compilation rules ---
# Depend on the buildroot compiler (order-only to avoid forced rebuild)

$(OVERLAY_DIR)/spectre: $(SPECTRE_SRC) | $(CC_ARM)
	@echo ">> Compiling Spectre Attack..."
	$(CC_ARM) -O2 $< -o $@

$(OVERLAY_DIR)/armageddon: $(ARMAGEDDON_SRC) | $(CC_ARM)
	@echo ">> Compiling Armageddon Attack..."
	$(CC_ARM) -O2 $< -o $@

$(OVERLAY_DIR)/meltdown: $(MELTDOWN_SRC) | $(CC_ARM)
	@echo ">> Compiling Meltdown Attack..."
	$(CC_ARM) -O2 $< -o $@

$(OVERLAY_DIR)/zombieload: $(ZOMBIELOAD_SRC) | $(CC_ARM)
	@echo ">> Compiling ZombieLoad Attack..."
	$(CC_ARM) -O2 $< -o $@

# --- Linux benchmark compilation rule ---
$(OVERLAY_DIR)/benchmark: $(BENCH_MAIN_SRC) $(BENCH_WRAPPER_SRC) $(BENCH_C_SRCS) | $(CC_ARM)
	@echo ">> Compiling Benchmark for Linux (VM3)..."
	$(CC_ARM) -O2 $(BENCH_INC_DIRS) $(BENCH_MAIN_SRC) $(BENCH_WRAPPER_SRC) $(BENCH_C_SRCS) -o $@ -lm

# --- IPC tools compilation rules ---
$(OVERLAY_DIR)/ipc_signal: $(OVERLAY_DIR)/ipc_signal.c | $(CC_ARM)
	@echo ">> Compiling ipc_signal..."
	$(CC_ARM) -O2 $< -o $@

$(OVERLAY_DIR)/ipc_sync: $(OVERLAY_DIR)/ipc_sync.c | $(CC_ARM)
	@echo ">> Compiling ipc_sync..."
	$(CC_ARM) -O2 $< -o $@

# --- attack_mode.cfg rule ---
# Reads the SCENARIO from regulation.h and writes the mode to the overlay
REGULATION_H := $(ROOT_DIR)/../../guest_common/inc/regulation.h
ATTACK_MODE_CFG := $(OVERLAY_DIR)/attack_mode.cfg

$(ATTACK_MODE_CFG): $(REGULATION_H)
	@SCENARIO=$$(grep -oP '^\s*#define\s+SCENARIO\s+\K[0-9]+' $(REGULATION_H)); \
	if [ "$$SCENARIO" = "12" ]; then \
		echo "manual" > $@; \
		echo ">> attack_mode.cfg: manual / standby (scenario 12)"; \
	elif [ "$$SCENARIO" = "11" ]; then \
		echo "random_periodic" > $@; \
		echo ">> attack_mode.cfg: random_periodic (scenario 11)"; \
	elif [ "$$SCENARIO" = "10" ]; then \
		echo "contention" > $@; \
		echo ">> attack_mode.cfg: contention (scenario 10)"; \
	elif [ "$$SCENARIO" = "8" ]; then \
		echo "meltdown_only" > $@; \
		echo ">> attack_mode.cfg: meltdown_only (scenario 8)"; \
	elif [ "$$SCENARIO" = "7" ]; then \
		echo "with_bench" > $@; \
		echo ">> attack_mode.cfg: with_bench (scenario 7)"; \
	else \
		echo "no_idle" > $@; \
		echo ">> attack_mode.cfg: no_idle (scenario $$SCENARIO)"; \
	fi

# --- RootFS rule ---

$(BUILDROOT_DIR)/output/images/rootfs.cpio: $(CUSTOM_APPS) $(ATTACK_MODE_CFG) | $(BUILDROOT_DIR)
	@echo ">> Repacking the Linux filesystem with the attacks..."
	$(MAKE) -C $(BUILDROOT_DIR) BR2_ROOTFS_OVERLAY="$(CUSTOM_OVERLAY)"

# make.mk expects rootfs.cpio.gz, but buildroot generates rootfs.cpio without compression.
# Generate the .gz from the .cpio.
$(BUILDROOT_DIR)/output/images/rootfs.cpio.gz: $(BUILDROOT_DIR)/output/images/rootfs.cpio
	@echo ">> Compressing rootfs.cpio -> rootfs.cpio.gz..."
	gzip -k -f $<

all: $(CUSTOM_APPS) $(ATTACK_MODE_CFG) $(BUILDROOT_DIR)/output/images/rootfs.cpio $(TARGET)

VM3_DTS := $(BAO_DEMOS)/demos/linux+freertos/devicetrees/$(PLATFORM)/linux.dts

$(eval $(call build-linux, $(TARGET), $(VM3_DTS)))

clean:
	rm -f $(TARGET)
	rm -f $(wrkdir_demo_imgs)/*.dtb
	rm -f $(OVERLAY_DIR)/benchmark
	rm -f $(OVERLAY_DIR)/ipc_signal
	rm -f $(OVERLAY_DIR)/ipc_sync