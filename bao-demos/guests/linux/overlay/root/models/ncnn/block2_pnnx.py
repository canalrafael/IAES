# pnnx model stat
# model inputshape = [1,64,56,56]f32
# FLOPS = 823.187M
# memory OPS = 3.134M

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

        self.convbn2d_0 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=64, kernel_size=(3,3), out_channels=128, padding=(1,1), padding_mode='zeros', stride=(2,2))
        self.0_relu = nn.ReLU()
        self.convbn2d_1 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=128, kernel_size=(3,3), out_channels=128, padding=(1,1), padding_mode='zeros', stride=(1,1))
        self.convbn2d_2 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=64, kernel_size=(1,1), out_channels=128, padding=(0,0), padding_mode='zeros', stride=(2,2))
        self.pnnx_unique_0 = nn.ReLU()
        self.convbn2d_3 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=128, kernel_size=(3,3), out_channels=128, padding=(1,1), padding_mode='zeros', stride=(1,1))
        self.1_relu = nn.ReLU()
        self.convbn2d_4 = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=128, kernel_size=(3,3), out_channels=128, padding=(1,1), padding_mode='zeros', stride=(1,1))
        self.pnnx_unique_1 = nn.ReLU()

        archive = zipfile.ZipFile('/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block2.pnnx.bin', 'r')
        self.convbn2d_0.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_0.bias', (128), 'float32')
        self.convbn2d_0.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_0.weight', (128,64,3,3), 'float32')
        self.convbn2d_1.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_1.bias', (128), 'float32')
        self.convbn2d_1.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_1.weight', (128,128,3,3), 'float32')
        self.convbn2d_2.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_2.bias', (128), 'float32')
        self.convbn2d_2.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_2.weight', (128,64,1,1), 'float32')
        self.convbn2d_3.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_3.bias', (128), 'float32')
        self.convbn2d_3.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_3.weight', (128,128,3,3), 'float32')
        self.convbn2d_4.bias = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_4.bias', (128), 'float32')
        self.convbn2d_4.weight = self.load_pnnx_bin_as_parameter(archive, 'convbn2d_4.weight', (128,128,3,3), 'float32')
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
        v_2 = self.0_relu(v_1)
        v_3 = self.convbn2d_1(v_2)
        v_4 = self.convbn2d_2(v_0)
        v_5 = (v_3 + v_4)
        v_6 = self.pnnx_unique_0(v_5)
        v_7 = self.convbn2d_3(v_6)
        v_8 = self.1_relu(v_7)
        v_9 = self.convbn2d_4(v_8)
        v_10 = (v_9 + v_6)
        v_11 = self.pnnx_unique_1(v_10)
        return v_11

def export_torchscript():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 64, 56, 56, dtype=torch.float)

    mod = torch.jit.trace(net, v_0)
    mod.save("/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block2_pnnx.py.pt")

def export_onnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 64, 56, 56, dtype=torch.float)

    torch.onnx.export(net, v_0, "/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block2_pnnx.py.onnx", export_params=True, operator_export_type=torch.onnx.OperatorExportTypes.ONNX_ATEN_FALLBACK, opset_version=13, input_names=['in0'], output_names=['out0'])

def export_pnnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 64, 56, 56, dtype=torch.float)

    import pnnx
    pnnx.export(net, "/home/canal/github/IAES/prototype/stage2_bao/models/ncnn/block2_pnnx.py.pt", v_0)

def export_ncnn():
    export_pnnx()

@torch.no_grad()
def test_inference():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 64, 56, 56, dtype=torch.float)

    return net(v_0)

if __name__ == "__main__":
    print(test_inference())
