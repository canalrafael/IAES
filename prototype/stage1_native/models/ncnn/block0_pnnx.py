# pnnx model stat
# model inputshape = [1,3,224,224]f32
# FLOPS = 239.239M
# memory OPS = 3.572M

import os
import numpy as np
import tempfile, zipfile
import torch
import torch.nn as nn
import torch.nn.functional as F
try:
    import torchvision
    import torchaudio
except:
    pass

class Model(nn.Module):
    def __init__(self):
        super(Model, self).__init__()

        self.convbn2d_0 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=3, kernel_size=(7,7), out_channels=64, padding=(3,3), padding_mode='zeros', stride=(2,2))
        self.2 = nn.ReLU()
        self.3 = nn.MaxPool2d(ceil_mode=False, dilation=(1,1), kernel_size=(3,3), padding=(1,1), return_indices=False, stride=(2,2))

        archive = zipfile.ZipFile('/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block0.pnnx.bin', 'r')
        self.convbn2d_0.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_0.bias', (64), 'float32')
        self.convbn2d_0.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_0.weight', (64,3,7,7), 'float32')
        archive.close()

    def load_pnnx_bin_as_parameter(self, archive, key, shape, dtype, requires_grad=True):
        return nn.Parameter(self.load_pnnx_bin_as_tensor(archive, key, shape, dtype), requires_grad)

    def load_pnnx_bin_as_tensor(self, archive, key, shape, dtype):
        fd, tmppath = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as tmpf, archive.open(key) as keyfile:
            tmpf.write(keyfile.read())
        m = np.memmap(tmppath, dtype=dtype, mode='r', shape=shape).copy()
        os.remove(tmppath)
        return torch.from_numpy(m)

    def forward(self, v_0):
        v_1 = self.convbn2d_0(v_0)
        v_2 = self.2(v_1)
        v_3 = self.3(v_2)
        return v_3

def export_torchscript():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 224, 224, dtype=torch.float)

    mod = torch.jit.trace(net, v_0)
    mod.save("/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block0_pnnx.py.pt")

def export_onnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 224, 224, dtype=torch.float)

    torch.onnx.export(net, v_0, "/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block0_pnnx.py.onnx", export_params=True, operator_export_type=torch.onnx.OperatorExportTypes.ONNX_ATEN_FALLBACK, opset_version=13, input_names=['in0'], output_names=['out0'])

def export_pnnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 224, 224, dtype=torch.float)

    import pnnx
    pnnx.export(net, "/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block0_pnnx.py.pt", v_0)

def export_ncnn():
    export_pnnx()

@torch.no_grad()
def test_inference():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 224, 224, dtype=torch.float)

    return net(v_0)

if __name__ == "__main__":
    print(test_inference())
