NAME:=vm_2
ROOT_DIR:=$(realpath .)

.DEFAULT_GOAL := all

wrkdir_demo_imgs := $(ROOT_DIR)/build/$(PLATFORM)
TARGET := $(wrkdir_demo_imgs)/$(NAME).bin

wrkdir_src := $(ROOT_DIR)
bao_demos ?= $(BAO_DEMOS)

# VM2 is a lean Linux (buildroot default rootfs) that just boots to a shell and
# signals VM0 that it is up. The model + controller is dropped in here later.
include $(BAO_DEMOS)/guests/linux/make.mk

BUILDROOT_DIR := $(buildroot_src)
CC_ARM := $(BUILDROOT_DIR)/output/host/bin/aarch64-buildroot-linux-uclibc-gcc
CUSTOM_OVERLAY := $(ROOT_DIR)/custom_overlay
OVERLAY_DIR := $(CUSTOM_OVERLAY)/root

# Only the lightweight boot-done signal to VM0.
CUSTOM_APPS := $(OVERLAY_DIR)/ipc_signal

$(OVERLAY_DIR)/ipc_signal: $(OVERLAY_DIR)/ipc_signal.c | $(buildroot_image)
	$(CC_ARM) -O2 $< -o $@

# Repack the rootfs with the VM2 overlay (ipc_signal + S99boot).
$(BUILDROOT_DIR)/output/images/rootfs.cpio: $(CUSTOM_APPS) | $(buildroot_image)
	$(MAKE) -C $(BUILDROOT_DIR) BR2_ROOTFS_OVERLAY="$(CUSTOM_OVERLAY)"

# make.mk expects rootfs.cpio.gz, but buildroot generates rootfs.cpio without
# compression. Generate the .gz from the .cpio.
$(buildroot_initrd): $(BUILDROOT_DIR)/output/images/rootfs.cpio
	gzip -k -f $<

all: $(TARGET)

VM2_DTS := $(BAO_DEMOS)/demos/linux+freertos/devicetrees/$(PLATFORM)/linux_vm2.dts

$(eval $(call build-linux, $(TARGET), $(VM2_DTS)))

clean:
	rm -f $(TARGET)
	rm -f $(wrkdir_demo_imgs)/*.dtb
	rm -f $(OVERLAY_DIR)/ipc_signal
