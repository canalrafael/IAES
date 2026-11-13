"""
Dataset Loader & ImageNet Accuracy Evaluation Utility for ANS Split Inference
=============================================================================
Provides deterministic image sequences from an ImageNet validation folder
and tracks Top-1 and Top-5 classification accuracy frame-by-frame.
Automatically triggers dataset_downloader if images are not yet present.
"""

import os
import glob
import json
from typing import List, Tuple, Optional
from PIL import Image
import torch
import torchvision.transforms as transforms
from dataset_downloader import ensure_dataset


class DatasetEvaluator:
    def __init__(self, dataset_dir: str = 'models/dataset', class_index_path: str = 'models/imagenet_class_index.json', auto_download: bool = True):
        self.dataset_dir = dataset_dir
        self.class_index_path = class_index_path
        
        # Load ImageNet class index (id -> [wnid, class_name])
        self.class_map = {}
        if os.path.exists(class_index_path):
            with open(class_index_path, 'r', encoding='utf-8') as f:
                raw_idx = json.load(f)
                for k, v in raw_idx.items():
                    # Map integer index (int(k)) to int(k)
                    self.class_map[int(k)] = int(k)
                    # Map folder name (e.g. '0'..'999' or 'n01440764') to integer index
                    self.class_map[str(k)] = int(k)
                    self.class_map[v[0]] = int(k)

        # Auto-download/ensure 1000 validation images if not present
        if auto_download:
            ensure_dataset(self.dataset_dir, max_images=1000)

        # Collect image files: supports either dataset/*.jpg or dataset/<class_id>/*.jpg
        self.image_files: List[Tuple[str, int]] = []
        self._load_images()

        # ImageNet preprocessing transform
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # Metrics tracking
        self.total_evaluated = 0
        self.top1_correct = 0
        self.top5_correct = 0

    def _load_images(self):
        """Scans dataset directory. If empty, falls back to stock Golden Retriever sample."""
        if os.path.isdir(self.dataset_dir):
            extensions = ('*.jpg', '*.jpeg', '*.png', '*.JPEG', '*.PNG')
            found = []
            for ext in extensions:
                found.extend(glob.glob(os.path.join(self.dataset_dir, '**', ext), recursive=True))

            found = sorted(found)
            for f in found:
                parent = os.path.basename(os.path.dirname(f))
                # If folder is '0'..'999' or WordNet ID
                label = self.class_map.get(parent, 207) # fallback 207
                self.image_files.append((f, label))

        # Fallback if no images found
        if not self.image_files:
            fallback = 'models/Golden_Retriever_Hund_Dog.jpg'
            self.image_files = [(fallback, 207)]

    def get_frame(self, frame_index: int) -> Tuple[torch.Tensor, int, str]:
        """Returns preprocessed input tensor, ground-truth label, and file path for frame_index."""
        # 1-indexed to 0-indexed modulo
        idx = (frame_index - 1) % len(self.image_files)
        path, label = self.image_files[idx]
        raw_img = Image.open(path).convert('RGB')
        tensor = self.transform(raw_img).unsqueeze(0)
        return tensor, label, path

    def update_accuracy(self, output_logits: torch.Tensor, ground_truth: int) -> Tuple[bool, bool, float, float]:
        """Computes Top-1 and Top-5 accuracy for current inference."""
        self.total_evaluated += 1
        
        if output_logits.dim() == 1:
            output_logits = output_logits.unsqueeze(0)

        _, pred_top5 = output_logits.topk(5, 1, True, True)
        pred_top5 = pred_top5.view(-1).tolist()

        is_top1 = (pred_top5[0] == ground_truth)
        is_top5 = (ground_truth in pred_top5)

        if is_top1:
            self.top1_correct += 1
        if is_top5:
            self.top5_correct += 1

        top1_acc = (self.top1_correct / self.total_evaluated) * 100.0
        top5_acc = (self.top5_correct / self.total_evaluated) * 100.0
        return is_top1, is_top5, top1_acc, top5_acc
