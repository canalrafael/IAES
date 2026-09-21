NAME:=vm_2
ROOT_DIR:=$(realpath .)

.DEFAULT_GOAL := all

wrkdir_demo_imgs := $(ROOT_DIR)/build/$(PLATFORM)
TARGET := $(wrkdir_demo_imgs)/$(NAME).bin

wrkdir_src := $(ROOT_DIR)
bao_demos ?= $(BAO_DEMOS)

include $(BAO_DEMOS)/guests/linux/make.mk

# make.mk expects rootfs.cpio.gz, but buildroot generates rootfs.cpio without compression.
# Generate the .gz from the .cpio.
$(buildroot_initrd): $(buildroot_image)
	gzip -k -f $(buildroot_src)/output/images/rootfs.cpio

all: $(TARGET)

VM2_DTS := $(BAO_DEMOS)/demos/linux+freertos/devicetrees/$(PLATFORM)/linux_vm2.dts

$(eval $(call build-linux, $(TARGET), $(VM2_DTS)))

clean:
	rm -f $(TARGET)
	rm -f $(wrkdir_demo_imgs)/*.dtb
