"""
Go/No-Go Experiment: Adversarial Manipulation of Adaptive Split Inference
=========================================================================
Implements the exact 10-step protocol defined in Section 1.18 of
IdeaRafaelSplit.pdf to verify that co-resident microarchitectural contention
during the controller's profiling phase induces a suboptimal partition point (k^a != k^0)
and causes persistent control amplification (Delta^probe_ctrl > 0).
"""

import argparse
import sys
import time
from typing import Dict, List, Tuple
import numpy as np
import torch

from split_inference.attack.stressor import MemoryContentionStressor
from split_inference.client import SplitInferenceClient
from split_inference.network.server import EdgeInferenceServer


def evaluate_split_point(
    client: SplitInferenceClient,
    k: int,
    num_samples: int = 10,
    stressor: MemoryContentionStressor = None
) -> float:
    """Measures the average latency J(k, a) over multiple inferences without updating controller."""
    latencies = []
    dummy_input = torch.randn(1, 3, 224, 224)

    for _ in range(num_samples):
        _, record = client.run_inference(dummy_input, forced_k=k, update_controller=False)
        latencies.append(record.total_latency_ms)

    return float(np.mean(latencies))


def run_single_trial(
    server_port: int,
    stressor_workers: int = 4,
    nominal_rounds: int = 40,
    attack_burst_rounds: int = 10,
    eval_samples: int = 15,
    network_rtt_ms: float = 5.0,
    network_bw_mbps: float = 100.0,
    edge_slowdown_factor: float = 4.0
) -> Dict[str, float]:
    """Executes one complete Go/No-Go trial."""
    # 1. Start clean client with emulated network conditions
    client = SplitInferenceClient(
        server_port=server_port,
        network_rtt_ms=network_rtt_ms,
        network_bw_mbps=network_bw_mbps,
        edge_slowdown_factor=edge_slowdown_factor
    )
    client.connect()
    dummy_input = torch.randn(1, 3, 224, 224)

    # 2. Phase 1: Nominal Learning (no attack)
    for _ in range(nominal_rounds):
        client.run_inference(dummy_input, update_controller=True)

    # Observe nominal decision k^0
    k_0 = client.controller.getEstimationAction(key_frame=True, current_frame=client.frame_idx + 1)
    j_k0_benign = evaluate_split_point(client, k_0, num_samples=eval_samples)

    # 3. Phase 2: Contention Attack during Profiling Phase (a^probe)
    stressor = MemoryContentionStressor(num_workers=stressor_workers, buffer_mb=32)
    stressor.start()
    try:
        # Client performs profiling/decision rounds while contention is active
        for _ in range(attack_burst_rounds):
            client.run_inference(dummy_input, update_controller=True)
        # Controller forms attacked decision k^a
        k_a = client.controller.getEstimationAction(key_frame=True, current_frame=client.frame_idx + 1)
        j_k0_attacked = evaluate_split_point(client, k_0, num_samples=eval_samples)
    finally:
        # 4. Stop attack immediately! Contention turns OFF.
        stressor.stop()

    # 5. Phase 3: Post-Attack Evaluation (Clean environment, zero contention)
    j_ka_benign = evaluate_split_point(client, k_a, num_samples=eval_samples)
    client.close()

    # 6. Formal Metric Calculations (Section 1.7 of IdeaRafaelSplit.pdf)
    # Direct physical slowdown: Delta_phys = J(k^0, a) - J(k^0, 0)
    delta_phys = max(0.0, j_k0_attacked - j_k0_benign)
    # Control-induced amplification: Delta^probe_ctrl = J(k^a, 0) - J(k^0, 0)
    delta_probe_ctrl = j_ka_benign - j_k0_benign
    # Decision changed?
    decision_changed = (k_a != k_0)

    return {
        "k_0": k_0,
        "k_a": k_a,
        "decision_changed": 1.0 if decision_changed else 0.0,
        "J_k0_benign_ms": j_k0_benign,
        "J_k0_attacked_ms": j_k0_attacked,
        "J_ka_benign_ms": j_ka_benign,
        "delta_phys_ms": delta_phys,
        "delta_probe_ctrl_ms": delta_probe_ctrl
    }


def main():
    parser = argparse.ArgumentParser(description="Go/No-Go Experiment for Adversarial Split Inference")
    parser.add_argument("--trials", type=int, default=5, help="Number of experimental trials")
    parser.add_argument("--workers", type=int, default=4, help="Number of contention workers")
    parser.add_argument("--port", type=int, default=5005, help="Server port")
    parser.add_argument("--rtt", type=float, default=5.0, help="Emulated one-way RTT in ms (default 5ms = Ethernet Pi-to-PC)")
    parser.add_argument("--bw", type=float, default=100.0, help="Emulated uplink bandwidth in Mbps (default 100 = GbE)")
    parser.add_argument("--slowdown", type=float, default=4.0, help="Edge device slowdown factor vs PC (default 4.0 = Raspberry Pi 4)")
    args = parser.parse_args()

    print("=" * 80)
    print("GO/NO-GO EXPERIMENT: ADVERSARIAL MANIPULATION OF ADAPTIVE SPLIT INFERENCE")
    print("Model: Partitioned ResNet-18 (5 split points: k0 to k4)")
    print("Controller: Unmodified Autodidactic Neurosurgeon (ANS muLinUCB, WWW 2021)")
    print(f"Experimental Trials: {args.trials} | Contention Workers: {args.workers}")
    print(f"Network Emulation: RTT={args.rtt} ms | Bandwidth={args.bw} Mbps | Edge Slowdown={args.slowdown}x")
    print("=" * 80)

    # Start Edge Server
    server = EdgeInferenceServer(host="127.0.0.1", port=args.port)
    server.start(background=True)
    time.sleep(1.0)

    results = []
    try:
        for t in range(1, args.trials + 1):
            print(f"\n--- Running Trial {t}/{args.trials} ---")
            trial_res = run_single_trial(
                server_port=args.port,
                stressor_workers=args.workers,
                nominal_rounds=40,
                attack_burst_rounds=12,
                eval_samples=15,
                network_rtt_ms=args.rtt,
                network_bw_mbps=args.bw,
                edge_slowdown_factor=args.slowdown
            )
            results.append(trial_res)
            print(f"  Nominal Split k^0: {int(trial_res['k_0'])} | Attacked Split k^a: {int(trial_res['k_a'])}")
            print(f"  Split Changed: {'YES' if trial_res['decision_changed'] else 'NO'}")
            print(f"  J(k^0, 0) [Nominal Latency]:   {trial_res['J_k0_benign_ms']:.2f} ms")
            print(f"  J(k^0, a) [Direct Contention]: {trial_res['J_k0_attacked_ms']:.2f} ms")
            print(f"  J(k^a, 0) [Post-Attack Lat.]:  {trial_res['J_ka_benign_ms']:.2f} ms")
            print(f"  -> Delta_phys:                 {trial_res['delta_phys_ms']:+.2f} ms")
            print(f"  -> Delta^probe_ctrl:           {trial_res['delta_probe_ctrl_ms']:+.2f} ms")

    finally:
        server.stop()

    # Summary Statistics
    k0_list = [r["k_0"] for r in results]
    ka_list = [r["k_a"] for r in results]
    changed_rate = np.mean([r["decision_changed"] for r in results]) * 100.0
    delta_phys_mean = np.mean([r["delta_phys_ms"] for r in results])
    delta_phys_std = np.std([r["delta_phys_ms"] for r in results])
    delta_ctrl_mean = np.mean([r["delta_probe_ctrl_ms"] for r in results])
    delta_ctrl_std = np.std([r["delta_probe_ctrl_ms"] for r in results])

    print("\n" + "=" * 80)
    print("FINAL EXPERIMENTAL SUMMARY & GO/NO-GO VERDICT")
    print("=" * 80)
    print(f"Split Manipulation Success Rate (k^a != k^0): {changed_rate:.1f}%")
    print(f"Direct Contention Slowdown (Delta_phys):      {delta_phys_mean:.2f} +/- {delta_phys_std:.2f} ms")
    print(f"Control-Induced Damage (Delta^probe_ctrl):     {delta_ctrl_mean:.2f} +/- {delta_ctrl_std:.2f} ms")

    print("\nGO/NO-GO CRITERIA CHECK (Section 1.18 of IdeaRafaelSplit.pdf):")
    c1 = changed_rate > 50.0
    c2 = delta_ctrl_mean > 0.0
    print(f"  [1] Decision repeatedly manipulated (k^a != k^0): {'PASSED' if c1 else 'FAILED'} ({changed_rate:.1f}%)")
    print(f"  [2] Persistent post-attack cost (Delta^probe_ctrl > 0): {'PASSED' if c2 else 'FAILED'} ({delta_ctrl_mean:.2f} ms)")

    if c1 and c2:
        print("\n>>> OVERALL VERDICT: [GO] - RESEARCH HYPOTHESIS CONFIRMED! <<<")
        print("Microarchitectural contention during profiling successfully fools the unmodified")
        print("ANS controller, causing a persistent harmful split and measurable control amplification.")
    else:
        print("\n>>> OVERALL VERDICT: [NEEDS ADJUSTMENT] <<<")


if __name__ == "__main__":
    main()
