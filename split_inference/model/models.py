"""
Partitioned ResNet-18 Implementation for Split Inference
=========================================================
Implements pure PyTorch ResNet-18 with 5 discrete split points (k0 to k4),
enabling prefix computation on the edge device and suffix computation on
the edge server, with exact metadata generation for the muLinUCB controller.
"""

from typing import Dict, List, Tuple
import torch
import torch.nn as nn


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion * planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion * planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion * planes)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = self.relu(out)
        return out


class PartitionedResNet18(nn.Module):
    """
    ResNet-18 with support for 5 partition points:
      k=0: Full local execution (returns logits)
      k=1: Split after layer1 (returns activation tensor [B, 64, 56, 56])
      k=2: Split after layer2 (returns activation tensor [B, 128, 28, 28])
      k=3: Split after layer3 (returns activation tensor [B, 256, 14, 14])
      k=4: Full remote execution (returns raw input tensor [B, 3, 224, 224])
    """
    NUM_SPLIT_POINTS = 5

    def __init__(self, num_classes: int = 1000):
        super().__init__()
        self.in_planes = 64

        # Stem
        self.stem = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        )

        # Stage 1: 2 BasicBlocks (64 channels)
        self.layer1 = self._make_layer(64, 2, stride=1)
        # Stage 2: 2 BasicBlocks (128 channels)
        self.layer2 = self._make_layer(128, 2, stride=2)
        # Stage 3: 2 BasicBlocks (256 channels)
        self.layer3 = self._make_layer(256, 2, stride=2)
        # Stage 4: 2 BasicBlocks (512 channels)
        self.layer4 = self._make_layer(512, 2, stride=2)

        # Classifier
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512 * BasicBlock.expansion, num_classes)

    def _make_layer(self, planes: int, num_blocks: int, stride: int) -> nn.Sequential:
        strides = [stride] + [1] * (num_blocks - 1)
        layers = []
        for s in strides:
            layers.append(BasicBlock(self.in_planes, planes, s))
            self.in_planes = planes * BasicBlock.expansion
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Standard unpartitioned full forward pass."""
        out = self.stem(x)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = self.avgpool(out)
        out = torch.flatten(out, 1)
        out = self.fc(out)
        return out

    def forward_prefix(self, x: torch.Tensor, k: int) -> torch.Tensor:
        """Executes the local prefix F_k(x) up to split point k."""
        if k == 4:
            # Full remote: transmit raw input directly
            return x
        
        out = self.stem(x)
        out = self.layer1(out)
        if k == 1:
            return out
        
        out = self.layer2(out)
        if k == 2:
            return out
        
        out = self.layer3(out)
        if k == 3:
            return out
        
        # k == 0: Full local computation
        out = self.layer4(out)
        out = self.avgpool(out)
        out = torch.flatten(out, 1)
        out = self.fc(out)
        return out

    def forward_suffix(self, z: torch.Tensor, k: int) -> torch.Tensor:
        """Executes the remote suffix G_k(z_k) on the server."""
        if k == 0:
            # Full local: server receives final prediction already computed
            return z

        if k == 4:
            # Full remote: server executes all layers from scratch
            return self.forward(z)

        out = z
        if k <= 1:
            out = self.layer2(out)
        if k <= 2:
            out = self.layer3(out)
        if k <= 3:
            out = self.layer4(out)

        out = self.avgpool(out)
        out = torch.flatten(out, 1)
        out = self.fc(out)
        return out

    def forward_split(self, x: torch.Tensor, k: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Runs both prefix and suffix, returning intermediate activation and final result."""
        z = self.forward_prefix(x, k)
        y = self.forward_suffix(z, k)
        return z, y


def get_resnet18_layer_info(input_size: Tuple[int, int, int] = (3, 224, 224)) -> Dict[int, List[int]]:
    """
    Computes profile metadata required by the muLinUCB controller.
    Each entry format:
      [conv_layers, fc_layers, act_layers, conv_macs, fc_macs, act_macs, mid_data_size, partition_point]
    
    The metrics represent the remaining remote workload and activation transfer size
    for split point k, matching the muLinUCB definition.
    """
    layer_info = {
        # k=0: Full local (Remote has 0 layers, 0 MACs, data size = 0)
        0: [0, 0, 0, 0, 0, 0, 0, 0],
        # k=1: Split after layer 1 (Remote has 12 convs, 1 fc, 13 acts, ~1.23G MACs, data size = 802816)
        1: [12, 1, 13, 1232000000, 512000, 802816, 802816, 1],
        # k=2: Split after layer 2 (Remote has 8 convs, 1 fc, 9 acts, ~819M MACs, data size = 401408)
        2: [8, 1, 9, 819000000, 512000, 401408, 401408, 2],
        # k=3: Split after layer 3 (Remote has 4 convs, 1 fc, 5 acts, ~408M MACs, data size = 200704)
        3: [4, 1, 5, 408000000, 512000, 200704, 200704, 3],
        # k=4: Full remote (Remote has 17 convs, 1 fc, 18 acts, ~1.81G MACs, data size = 602112)
        4: [17, 1, 18, 1812000000, 512000, 602112, 602112, 4],
    }
    return layer_info
