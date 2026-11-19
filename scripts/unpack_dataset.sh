#!/usr/bin/env bash
# =============================================================================
# scripts/unpack_dataset.sh
#
# Ensures the ANS ImageNet validation subset (1 image per class, 1,000 total)
# is available in the VM2 Buildroot overlay.
#
# Priority order:
#   1. If dataset/ already has ≥ 1000 images → skip.
#   2. If a local tarball exists (scripts/dataset_assets/) → unpack it.
#   3. Otherwise → shallow-clone the public GitHub repo and populate.
#
# Usage:
#   ./scripts/unpack_dataset.sh           # default VM2 overlay path
#   ./scripts/unpack_dataset.sh <dest>    # custom destination
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARBALL_PATH="$REPO_ROOT/scripts/dataset_assets/imagenet_subset_1000.tar.gz"
DEFAULT_DEST="$REPO_ROOT/bao-demos/wrkdir/srcs/VMs/vm_2/custom_overlay/root/ans/models"
DEST="${1:-$DEFAULT_DEST}"
DATASET_DIR="$DEST/dataset"

REMOTE_REPO="https://github.com/ndb796/Small-ImageNet-Validation-Dataset-1000-Classes.git"
TEMP_CLONE="/tmp/small_imagenet_repo"

# ── Already present? ─────────────────────────────────────────────────────────
if [ -d "$DATASET_DIR" ]; then
    NUM_EXISTING=$(find "$DATASET_DIR" -type f 2>/dev/null | wc -l)
    if [ "$NUM_EXISTING" -ge 1000 ]; then
        echo "[unpack_dataset] Dataset already present ($NUM_EXISTING images). Skipping."
        exit 0
    else
        echo "[unpack_dataset] Dataset incomplete ($NUM_EXISTING images). Repopulating..."
        rm -rf "$DATASET_DIR"
    fi
fi

mkdir -p "$DEST"

# ── Method 1: Local tarball ──────────────────────────────────────────────────
if [ -f "$TARBALL_PATH" ]; then
    echo "[unpack_dataset] Found local tarball. Unpacking..."
    tar -xzf "$TARBALL_PATH" -C "$DEST"
    NUM_IMAGES=$(find "$DATASET_DIR" -type f | wc -l)
    echo "[unpack_dataset] Done. $NUM_IMAGES images available."
    exit 0
fi

# ── Method 2: Download from public GitHub repo ──────────────────────────────
echo "[unpack_dataset] No local tarball found. Downloading from:"
echo "  $REMOTE_REPO"

rm -rf "$TEMP_CLONE"
git clone --depth 1 "$REMOTE_REPO" "$TEMP_CLONE"

SRC_DIR="$TEMP_CLONE"
# The repo may have a subfolder for images
if [ -d "$TEMP_CLONE/ILSVRC2012_img_val_subset" ]; then
    SRC_DIR="$TEMP_CLONE/ILSVRC2012_img_val_subset"
fi

mkdir -p "$DATASET_DIR"
COUNT=0
for CLASS_FOLDER in "$SRC_DIR"/*/; do
    [ -d "$CLASS_FOLDER" ] || continue
    CLASS_NAME="$(basename "$CLASS_FOLDER")"

    # Skip non-image directories (e.g. .git)
    case "$CLASS_NAME" in .git*|__*) continue ;; esac

    IMG=$(find "$CLASS_FOLDER" -maxdepth 1 -type f \( -name '*.JPEG' -o -name '*.jpg' -o -name '*.png' \) | sort | head -1)
    if [ -n "$IMG" ]; then
        TARGET_DIR="$DATASET_DIR/$CLASS_NAME"
        mkdir -p "$TARGET_DIR"
        cp "$IMG" "$TARGET_DIR/"
        COUNT=$((COUNT + 1))
    fi
    [ "$COUNT" -ge 1000 ] && break
done

rm -rf "$TEMP_CLONE"

echo "[unpack_dataset] Done. $COUNT images downloaded to:"
echo "  $DATASET_DIR"
echo ""
echo "(Optional) To create a local tarball for offline use:"
echo "  ./scripts/pack_dataset.sh"
