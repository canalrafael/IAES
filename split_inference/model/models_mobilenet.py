"""
Partitioned MobileNetV2 for Split Inference
============================================
Provides the same forward_prefix / forward_suffix / get_layer_info interface
as models.py (ResNet-18), making MobileNetV2 a drop-in second DNN for the
Stage 2 attack campaign.

Split points are chosen at inverted-residual block group boundaries, giving
a range of activation tensor sizes similar to ResNet-18:

  k=0  Full local     — no network transfer, all compute on edge device
  k=1  After features[3]  — 24-ch 56×56 bottleneck (14,112 elements)
  k=2  After features[6]  — 32-ch 28×28 block     (25,088 elements)
  k=3  After features[13] — 96-ch 14×14 block     (18,816 elements)
  k=4  Full remote    — raw input 3×224×224 sent to server (150,528 elements)

The muLinUCB controller's layer_info table is populated with realistic MACs
and layer-count estimates so the bandit's context features are meaningful.
"""

from dataclasses import dataclass
from typing import Dict, List

import torch
import torch.nn as nn
import torchvision.models as tvm


# ─────────────────────────────────────────────────────────────────────────────
# Layer info for muLinUCB context features
# ─────────────────────────────────────────────────────────────────────────────

def get_mobilenetv2_layer_info() -> Dict[int, dict]:
    """
    Returns the layer_info dict consumed by the ANS muLinUCB controller.
    Format mirrors get_resnet18_layer_info() in models.py.

    Keys per split point k:
        num_layer   — cumulative layers on edge device
        num_mac     — cumulative MACs on edge device (millions, approximate)
        data_size   — activation tensor size in bytes
    """
    # Approximate cumulative MACs (millions) per prefix for 224×224 input
    # Reference: MobileNetV2 total ≈ 300M MACs for 224×224
    return {
        0: {  # Full local
            "num_layer": 52,   # all inverted residuals + classifier
            "num_mac": 300.0,
            "data_size": 4 * 1000,  # logits: 1000 floats
        },
        1: {  # After features[3] — 24-ch 56×56
            "num_layer": 7,
            "num_mac": 42.0,
            "data_size": 4 * 24 * 56 * 56,  # 301,056 bytes
        },
        2: {  # After features[6] — 32-ch 28×28
            "num_layer": 14,
            "num_mac": 92.0,
            "data_size": 4 * 32 * 28 * 28,  # 100,352 bytes
        },
        3: {  # After features[13] — 96-ch 14×14
            "num_layer": 33,
            "num_mac": 210.0,
            "data_size": 4 * 96 * 14 * 14,  # 75,264 bytes
        },
        4: {  # Full remote — raw input 3×224×224
            "num_layer": 0,
            "num_mac": 0.0,
            "data_size": 4 * 3 * 224 * 224,  # 602,112 bytes
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Partitioned MobileNetV2
# ─────────────────────────────────────────────────────────────────────────────

# Inclusive end-indices into model.features for each prefix k
_PREFIX_END = {
    0: None,   # full local  — entire model
    1: 3,      # features[0..3]
    2: 6,      # features[0..6]
    3: 13,     # features[0..13]
    4: -1,     # full remote — no local features
}


class PartitionedMobileNetV2(nn.Module):
    """
    MobileNetV2 partitioned into (prefix, suffix) pairs for split inference.

    The model is loaded from torchvision (pre-trained weights optional) and
    split at a chosen cut point k. The prefix F_k(x) runs on the edge device;
    the suffix G_k(z_k) runs on the server.

    No modifications are made to any MobileNetV2 layer — only the execution
    is split, not the architecture.
    """

    def __init__(self, pretrained: bool = False):
        super().__init__()
        weights = tvm.MobileNet_V2_Weights.DEFAULT if pretrained else None
        base = tvm.mobilenet_v2(weights=weights)

        # Store feature blocks and classifier as sequential containers
        self.features: nn.Sequential = base.features  # 19 blocks (0..18)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier: nn.Sequential = base.classifier

    # ── prefix ──────────────────────────────────────────────────────────────

    def forward_prefix(self, x: torch.Tensor, k: int) -> torch.Tensor:
        """
        Runs F_k(x): the edge-side prefix computation up to split point k.

        Args:
            x:  Input image tensor [B, 3, 224, 224]
            k:  Split point index ∈ {0, 1, 2, 3, 4}

        Returns:
            z_k:  Intermediate activation (or final logits for k=0)
        """
        if k == 0:
            # Full local: run entire forward pass on edge
            z = self.features(x)
            z = self.pool(z).flatten(1)
            return self.classifier(z)

        if k == 4:
            # Full remote: send raw input as-is
            return x

        # Partial prefix: run features[0..end]
        end = _PREFIX_END[k]
        z = x
        for block in self.features[: end + 1]:
            z = block(z)
        return z

    # ── suffix ───────────────────────────────────────────────────────────────

    def forward_suffix(self, z: torch.Tensor, k: int) -> torch.Tensor:
        """
        Runs G_k(z_k): the server-side suffix computation.

        Args:
            z:  Intermediate activation received from the edge client
            k:  Split point index (must match the prefix that produced z)

        Returns:
            logits: Final class logits [B, 1000]
        """
        if k == 0:
            # Should not be called for full-local; return z unchanged
            return z

        if k == 4:
            # Full remote: z is the raw input — run the entire network
            out = self.features(z)
            out = self.pool(out).flatten(1)
            return self.classifier(out)

        # Continue from where the prefix stopped
        end = _PREFIX_END[k]
        out = z
        for block in self.features[end + 1 :]:
            out = block(out)
        out = self.pool(out).flatten(1)
        return self.classifier(out)

    # ── full forward (validation) ────────────────────────────────────────────

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Unpartitioned forward pass — used only for numerical equivalence checks."""
        z = self.features(x)
        z = self.pool(z).flatten(1)
        return self.classifier(z)
