#!/usr/bin/env bash
# Stage the Apparate replay controller + one experiment's pickles into the VM2
# buildroot overlay, so they are baked into the VM2 rootfs. Run before building
# VM2 (./build.sh vm 2). The staged payload is gitignored (code is in the
# submodule; pickles are large).
#
# Usage: scripts/stage_apparate_vm2.sh [ARCH] [DATASET]   (default: resnet18 auburn)
set -euo pipefail
ARCH="${1:-resnet18}"
DATASET="${2:-auburn}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/apparate-ae"
DEST="$REPO/bao-demos/wrkdir/srcs/VMs/vm_2/custom_overlay/root/apparate-ae"

echo ">> staging $ARCH / $DATASET into $DEST"
rm -rf "$DEST"
mkdir -p "$DEST/apparate" "$DEST/apparate/logs" "$DEST/apparate_latency" \
         "$DEST/profile_pickles_bs" "$DEST/simulation_pickles" \
         "$DEST/bootstrap_pickles" "$DEST/batch_decisions"

# Controller code (exactly the layout proven to run numpy-only), minus bulk.
cp -r "$SRC/apparate/." "$DEST/apparate/"
rm -rf "$DEST/apparate/.git" "$DEST/apparate/logs"/* 2>/dev/null || true
find "$DEST/apparate" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
# Experiment glue (importable from the controller's dir): the live-latency
# source and the VM0 status relay.
cp "$SRC/contention_sources.py" "$DEST/apparate/contention_sources.py"
cp "$SRC/ipc_report.py"         "$DEST/apparate/ipc_report.py"
cp "$SRC/live_latency.py"       "$DEST/apparate/live_latency.py"

# Pickles for this one experiment (~11 MB).
cp "$SRC"/profile_pickles_bs/${ARCH}_*.pickle            "$DEST/profile_pickles_bs/"
cp "$SRC"/simulation_pickles/${DATASET}_${ARCH}.pickle    "$DEST/simulation_pickles/"
cp "$SRC"/bootstrap_pickles/bootstrap_${DATASET}_${ARCH}.pickle "$DEST/bootstrap_pickles/"
cp "$SRC"/batch_decisions/${ARCH}_1_fixed_30.pickle       "$DEST/batch_decisions/"

echo ">> staged size: $(du -sh "$DEST" | cut -f1)"
echo ">> done. Now build VM2:  ./build.sh vm 2"
