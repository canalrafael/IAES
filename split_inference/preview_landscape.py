"""
Latency Landscape Preview — with Pi 4 emulation
================================================
Shows the expected total latency per split point under different edge/network
configurations. Used to tune the --rtt, --bw, --slowdown parameters before
running the full Go/No-Go experiment.

Local prefix times measured on THIS PC. Edge slowdown multiplies them.
Server suffix times measured on this PC (server runs here in emulation).
"""
import torch, time, sys
sys.path.insert(0, '.')
from split_inference.model.models import PartitionedResNet18

model = PartitionedResNet18()
model.eval()

# Measure actual PC prefix times
shapes = {
    0: [1, 1000],
    1: [1, 64, 56, 56],
    2: [1, 128, 28, 28],
    3: [1, 256, 14, 14],
    4: [1, 3, 224, 224]
}
inputs = {k: torch.randn(*s) for k, s in shapes.items()}

print("Measuring local prefix times...")
local_ms = {}
for k in range(5):
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        with torch.no_grad():
            model.forward_prefix(torch.randn(1, 3, 224, 224), k)
        times.append((time.perf_counter()-t0)*1000)
    local_ms[k] = sum(times)/len(times)

print("Measuring server suffix times...")
server_ms = {0: 0.0}
for k in range(1, 5):
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        with torch.no_grad():
            model.forward_suffix(inputs[k], k)
        times.append((time.perf_counter()-t0)*1000)
    server_ms[k] = sum(times)/len(times)

scenarios = [
    ("100 Mbps / 5 ms RTT, 4x slowdown  (GbE, Pi 4)", 5.0, 100.0, 4.0),
    ("100 Mbps / 5 ms RTT, 1x slowdown  (loopback only)", 5.0, 100.0, 1.0),
    (" 20 Mbps / 20 ms RTT, 4x slowdown (Wi-Fi, Pi 4)", 20.0, 20.0, 4.0),
]

for label, rtt_ms, bw_mbps, slowdown in scenarios:
    print(f"\n=== {label} ===")
    print(f"{'k':>3}  {'PC ms':>7}  {'Pi ms':>7}  {'Size kB':>8}  {'Net ms':>8}  {'Server ms':>10}  {'Total ms':>10}")
    print("-" * 68)
    for k in range(5):
        t = torch.zeros(shapes[k])
        bytes_ = t.nelement() * 4
        kb = bytes_ / 1024
        pi_ms = local_ms[k] * slowdown
        if k == 0:
            net_ms = 0.0
            total = pi_ms
        else:
            net_ms = rtt_ms + (bytes_ * 8) / (bw_mbps * 1e6) * 1000
            total = pi_ms + net_ms + server_ms[k]
        print(f"{k:>3}  {local_ms[k]:>7.1f}  {pi_ms:>7.1f}  {kb:>8.1f}  {net_ms:>8.1f}  {server_ms[k]:>10.1f}  {total:>10.1f}")
    # Best split
    totals = {}
    for k in range(5):
        t = torch.zeros(shapes[k])
        bytes_ = t.nelement() * 4
        pi_ms = local_ms[k] * slowdown
        net_ms = (rtt_ms + (bytes_*8)/(bw_mbps*1e6)*1000) if k > 0 else 0.0
        totals[k] = pi_ms + (net_ms + server_ms[k] if k > 0 else 0.0)
    best_k = min(totals, key=lambda k: totals[k])
    print(f"  => Baseline winner: k={best_k}  ({totals[best_k]:.1f} ms)")
    
    # What happens if local cost increases 3x (contention on Pi)?
    print(f"  Under 3x CPU contention on Pi:")
    totals_attack = {}
    for k in range(5):
        t = torch.zeros(shapes[k])
        bytes_ = t.nelement() * 4
        pi_ms = local_ms[k] * slowdown * 3  # contention
        net_ms = (rtt_ms + (bytes_*8)/(bw_mbps*1e6)*1000) if k > 0 else 0.0
        totals_attack[k] = pi_ms + (net_ms + server_ms[k] if k > 0 else 0.0)
    best_k_att = min(totals_attack, key=lambda k: totals_attack[k])
    print(f"  => Attacked winner: k={best_k_att}  ({totals_attack[best_k_att]:.1f} ms)")
    if best_k != best_k_att:
        print(f"  !!! SHIFT ACHIEVABLE: k={best_k} -> k={best_k_att} !!!")
