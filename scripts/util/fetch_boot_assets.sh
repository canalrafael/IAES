#!/usr/bin/env bash
set -euo pipefail

VM_INDEX=NULL source ./env.bash

FIRMWARE_REPO="https://github.com/raspberrypi/firmware.git"
UBOOT_REPO="https://github.com/u-boot/u-boot.git"
UBOOT_TAG="v2022.10"
ATF_REPO="https://github.com/bao-project/arm-trusted-firmware.git"
ATF_BRANCH="bao/demo"

mkdir -p "$BAO_DEMOS_WRKDIR_PLAT"

if [[ -d "$BAO_DEMOS_FW/boot" ]]; then
    echo "Firmware already present at $BAO_DEMOS_FW/boot, skipping."
else
    echo "Fetching Raspberry Pi firmware..."
    rm -rf "$BAO_DEMOS_FW"
    git clone --depth 1 --filter=blob:none --sparse "$FIRMWARE_REPO" "$BAO_DEMOS_FW"
    git -C "$BAO_DEMOS_FW" sparse-checkout set boot
    echo "Firmware fetched."
fi

if [[ -f "$BAO_DEMOS_WRKDIR_PLAT/u-boot.bin" ]]; then
    echo "u-boot.bin already present, skipping."
else
    if [[ ! -d "$BAO_DEMOS_UBOOT" ]]; then
        echo "Cloning u-boot..."
        git clone --depth 1 --branch "$UBOOT_TAG" "$UBOOT_REPO" "$BAO_DEMOS_UBOOT"
    fi
    echo "Building u-boot..."
    make -C "$BAO_DEMOS_UBOOT" CROSS_COMPILE="$CROSS_COMPILE" rpi_4_defconfig
    make -C "$BAO_DEMOS_UBOOT" CROSS_COMPILE="$CROSS_COMPILE" -j"$(nproc)"
    cp "$BAO_DEMOS_UBOOT/u-boot.bin" "$BAO_DEMOS_WRKDIR_PLAT"
    echo "u-boot.bin built."
fi

if [[ -f "$BAO_DEMOS_WRKDIR_PLAT/bl31.bin" ]]; then
    echo "bl31.bin already present, skipping."
else
    if [[ ! -d "$BAO_DEMOS_ATF" ]]; then
        echo "Cloning arm-trusted-firmware..."
        git clone --depth 1 --branch "$ATF_BRANCH" "$ATF_REPO" "$BAO_DEMOS_ATF"
    fi
    echo "Building bl31.bin..."
    make -C "$BAO_DEMOS_ATF" PLAT=rpi4 CROSS_COMPILE="$CROSS_COMPILE"
    cp "$BAO_DEMOS_ATF/build/rpi4/release/bl31.bin" "$BAO_DEMOS_WRKDIR_PLAT"
    echo "bl31.bin built."
fi

echo "Boot assets ready at $BAO_DEMOS_WRKDIR_PLAT"
