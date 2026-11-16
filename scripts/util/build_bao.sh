#!/usr/bin/env bash

VM_INDEX=9 source ./env.bash  # index is not used anyway

mkdir -p $BAO_DEMOS_WRKDIR_IMGS/config

cp -L $BAO_DEMOS/demos/$DEMO/configs/$PLATFORM.c\
    $BAO_DEMOS_WRKDIR_IMGS/config/$DEMO.c

make -C $BAO_DEMOS_BAO\
    PLATFORM=$PLATFORM\
    RPI4_MEM_GB=8\
    CONFIG_REPO=$BAO_DEMOS_WRKDIR_IMGS/config\
    CONFIG=$DEMO\
    CPPFLAGS=-DBAO_DEMOS_WRKDIR_IMGS=$BAO_DEMOS_WRKDIR_IMGS

cp $BAO_DEMOS_BAO/bin/$PLATFORM/$DEMO/bao.bin\
    $BAO_DEMOS_WRKDIR_IMGS
