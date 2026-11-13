"""
Automatic ImageNet Validation Dataset Downloader & Preparer for ANS
===================================================================
Automatically checks if the ImageNet validation subset is present.
If not, clones/downloads 1 image per class (1,000 images total)
from ndb796/Small-ImageNet-Validation-Dataset-1000-Classes.
"""

import os
import sys
import glob
import shutil
import subprocess

REPO_URL = "https://github.com/ndb796/Small-ImageNet-Validation-Dataset-1000-Classes.git"


def ensure_dataset(dataset_dir: str = 'models/dataset', max_images: int = 1000) -> str:
    """Ensures dataset directory exists and contains at least 1,000 images."""
    os.makedirs(dataset_dir, exist_ok=True)
    existing_images = glob.glob(os.path.join(dataset_dir, '**', '*.JPEG'), recursive=True) + \
                      glob.glob(os.path.join(dataset_dir, '**', '*.jpg'), recursive=True) + \
                      glob.glob(os.path.join(dataset_dir, '**', '*.png'), recursive=True)

    if len(existing_images) >= max_images:
        print(f"[DATASET] Found existing dataset with {len(existing_images)} images in {dataset_dir}.")
        return dataset_dir

    print(f"\n[DATASET-AUTO] Dataset has {len(existing_images)} images. Need {max_images}.")
    print(f"[DATASET-AUTO] Automatically cloning lightweight validation subset from:")
    print(f"               {REPO_URL}")

    temp_clone_dir = "/tmp/small_imagenet_repo"
    if os.path.exists(temp_clone_dir):
        shutil.rmtree(temp_clone_dir, ignore_errors=True)

    try:
        # Clone shallow (depth 1) to save bandwidth and storage
        cmd = ["git", "clone", "--depth", "1", REPO_URL, temp_clone_dir]
        subprocess.run(cmd, check=True)
        
        src_subset_dir = os.path.join(temp_clone_dir, "ILSVRC2012_img_val_subset")
        if not os.path.isdir(src_subset_dir):
            src_subset_dir = temp_clone_dir

        # Copy 1 image per class directory into dataset_dir
        count = 0
        for entry in sorted(os.listdir(src_subset_dir)):
            class_folder = os.path.join(src_subset_dir, entry)
            if os.path.isdir(class_folder):
                imgs = sorted(os.listdir(class_folder))
                if imgs:
                    target_class_dir = os.path.join(dataset_dir, entry)
                    os.makedirs(target_class_dir, exist_ok=True)
                    # Take 1 image per class up to max_images
                    shutil.copy2(os.path.join(class_folder, imgs[0]), os.path.join(target_class_dir, imgs[0]))
                    count += 1
                    if count >= max_images:
                        break

        print(f"[DATASET-AUTO] Successfully imported {count} validation images into {dataset_dir}!")
        shutil.rmtree(temp_clone_dir, ignore_errors=True)
        return dataset_dir

    except Exception as e:
        print(f"[DATASET-AUTO WARNING] Could not auto-download repository ({e}).")
        print(f"[DATASET-AUTO WARNING] Falling back to default built-in images.")
        return dataset_dir


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'models/dataset'
    ensure_dataset(target)

