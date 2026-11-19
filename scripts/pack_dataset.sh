#!/usr/bin/env bash
# =============================================================================
# scripts/pack_dataset.sh
#
# Packs the ANS ImageNet validation subset (1 image per class, 1,000 total)
# from the VM2 Buildroot overlay into a compressed tarball stored in the repo.
#
# Run this ONCE on your development machine whenever the dataset changes.
# The tarball is committed to git and unpacked on-demand via unpack_dataset.sh.
#
# Usage:
#   ./scripts/pack_dataset.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DATASET_SRC="$REPO_ROOT/bao-demos/wrkdir/srcs/VMs/vm_2/custom_overlay/root/ans/models/dataset"
TARBALL_DIR="$REPO_ROOT/scripts/dataset_assets"
TARBALL_PATH="$TARBALL_DIR/imagenet_subset_1000.tar.gz"

# ── Checks ───────────────────────────────────────────────────────────────────
if [ ! -d "$DATASET_SRC" ]; then
    echo "ERROR: Dataset source not found at:"
    echo "  $DATASET_SRC"
    echo "Run the ANS client on the Pi first to trigger auto-download, or"
    echo "manually clone https://github.com/ndb796/Small-ImageNet-Validation-Dataset-1000-Classes"
    exit 1
fi

NUM_IMAGES=$(find "$DATASET_SRC" -type f | wc -l)
echo "[pack_dataset] Found $NUM_IMAGES images in dataset."

if [ "$NUM_IMAGES" -lt 100 ]; then
    echo "WARNING: Fewer than 100 images found. Dataset may be incomplete."
fi

# ── Pack ─────────────────────────────────────────────────────────────────────
mkdir -p "$TARBALL_DIR"

echo "[pack_dataset] Creating tarball at:"
echo "  $TARBALL_PATH"

tar -czf "$TARBALL_PATH" \
    -C "$DATASET_SRC/.." \
    dataset

SIZE=$(du -sh "$TARBALL_PATH" | cut -f1)
echo "[pack_dataset] Done. Tarball size: $SIZE"
echo ""
echo "Next steps:"
echo "  git add scripts/dataset_assets/imagenet_subset_1000.tar.gz"
echo "  git commit -m 'dataset: add ImageNet validation subset (1000 images, 1 per class)'"
