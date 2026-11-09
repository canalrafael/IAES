#!/usr/bin/env bash

input=$1

VM_INDEX='all'  # Initialize VM_INDEX
VM_NAME_PREFIX="vm_"
build_all=false # Initialize build_all

# Check if input is a number from 0 to 3
if [[ "$input" =~ ^[0-3]$ ]]; then
  VM_INDEX="$input"
  echo "Building VM index: $VM_INDEX"
elif [ "$input" == "all" ]; then
  build_all=true
  echo "Building all VMs..."
elif [ -n "$input" ]; then
  echo "Error: Invalid input. Must be 0-3 or 'all'." >&2
  exit 1
else
  echo "Error: No input provided." >&2
  exit 1
fi

# Function placeholder (replace with your actual build function)
build() {
  echo "Building VM with index: $1"
  #  Your actual build commands would go here,
  #  using $1 as the VM index.
  VM_INDEX=$1 source ./env.bash
  make -C $BAO_DEMOS_FREERTOS PLATFORM=$PLATFORM $FREERTOS_PARAMS && echo "Copying..." && mkdir -p $BAO_DEMOS_WRKDIR_IMGS && cp $BAO_DEMOS_FREERTOS/build/$PLATFORM/$VM_NAME_PREFIX$VM_INDEX.bin $BAO_DEMOS_WRKDIR_IMGS
}

# Build logic
failed=0
if "$build_all"; then
  for i in {0..3}; do
    VM_INDEX="$i" # important: set VM_INDEX inside the loop
    build "$VM_INDEX" || failed=1 #  Call your build command
  done
elif [ -n "$VM_INDEX" ]; then
  build "$VM_INDEX" || failed=1 # Call build command with the provided VM_INDEX
else
  echo "Error:  VM_INDEX is not defined." >&2
  exit 1
fi

echo "Finished. Results:"
find $BAO_DEMOS_WRKDIR_IMGS

# echo $CROSS_COMPILE
# export VM_INDEX=$1
# source ./env.bash
# make -C $BAO_DEMOS_FREERTOS PLATFORM=$PLATFORM $FREERTOS_PARAMS
# echo $CROSS_COMPILE

# Propagate make failures so build.sh does not report a stale image as built
exit $failed
