"""
Go/No-Go Hardware Experiment
============================
Executes the Go/No-Go prototype test on physical hardware (e.g., Raspberry Pi).
This script DOES NOT start a local server and uses ZERO artificial network emulation,
relying purely on the physical connection and the Pi's CPU execution speed.
"""

import argparse
import time
from typing import Dict
import numpy as np
import torch

from split_inference.attack.stressor import MemoryContentionStressor
from split_inference.client import SplitInferenceClient

def evaluate_split_point(
    client: SplitInferenceClient,
    k: int,
    num_samples: int = 10
) -> float:
    """Measures average latency J(k, a) without updating controller."""
    latencies = []
    dummy_input = torch.randn(1, 3, 224, 224)

    for _ in range(num_samples):
        _, record = client.run_inference(dummy_input, forced_k=k, update_controller=False)
        latencies.append(record.total_latency_ms)

    return float(np.mean(latencies))

def run_single_trial(
    server_host: str,
    server_port: int,
    stressor_workers: int = 4,
    nominal_rounds: int = 40,
    attack_burst_rounds: int = 10,
    eval_samples: int = 15
) -> Dict[str, float]:
    """Executes one complete Go/No-Go trial on hardware."""
    # 1. Start clean client with ZERO artificial network conditions
    client = SplitInferenceClient(
        server_host=server_host,
        server_port=server_port,
        network_rtt_ms=0.0,
        network_bw_mbps=0.0,
        edge_slowdown_factor=1.0  # We are on the real Pi, no slowdown needed
    )
    client.connect()
    dummy_input = torch.randn(1, 3, 224, 224)

    # 2. Phase 1: Nominal Learning (no attack)
    for _ in range(nominal_rounds):
        client.run_inference(dummy_input, update_controller=True)

    # Observe nominal decision k^0
    k_0 = client.controller.getEstimationAction(key_frame=True, current_frame=client.frame_idx + 1)
    j_k0_benign = evaluate_split_point(client, k_0, num_samples=eval_samples)

    # 3. Phase 2: Contention Attack (a^probe)
    stressor = MemoryContentionStressor(num_workers=stressor_workers, buffer_mb=32)
    stressor.start()
    try:
        # Client performs inferences while contention is active
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

    # 6. Formal Metric Calculations
    delta_phys = max(0.0, j_k0_attacked - j_k0_benign)
    delta_probe_ctrl = j_ka_benign - j_k0_benign
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
    parser = argparse.ArgumentParser(description="Go/No-Go Hardware Experiment")
    parser.add_argument("--trials", type=int, default=5, help="Number of experimental trials")
    parser.add_argument("--workers", type=int, default=4, help="Number of contention workers")
    parser.add_argument("--host", type=str, required=True, help="IP address of the Edge Server (PC)")
    parser.add_argument("--port", type=int, default=5005, help="Server port")
    args = parser.parse_args()

    print("=" * 80)
    print("GO/NO-GO EXPERIMENT: HARDWARE DEPLOYMENT")
    print(f"Connecting to PC Edge Server at: {args.host}:{args.port}")
    print("Artificial emulation: OFF")
    print("=" * 80)

    results = []
    for t in range(1, args.trials + 1):
        print(f"\n--- Running Trial {t}/{args.trials} ---")
        trial_res = run_single_trial(
            server_host=args.host,
            server_port=args.port,
            stressor_workers=args.workers,
            nominal_rounds=40,
            attack_burst_rounds=12,
            eval_samples=15
        )
        results.append(trial_res)
        print(f"  Nominal Split k^0: {int(trial_res['k_0'])} | Attacked Split k^a: {int(trial_res['k_a'])}")
        print(f"  Split Changed: {'YES' if trial_res['decision_changed'] else 'NO'}")
        print(f"  -> Delta_phys:                 {trial_res['delta_phys_ms']:+.2f} ms")
        print(f"  -> Delta^probe_ctrl:           {trial_res['delta_probe_ctrl_ms']:+.2f} ms")

    # Summary Statistics
    k0_list = [r["k_0"] for r in results]
    ka_list = [r["k_a"] for r in results]
    changed_rate = np.mean([r["decision_changed"] for r in results]) * 100.0
    delta_phys_mean = np.mean([r["delta_phys_ms"] for r in results])
    delta_ctrl_mean = np.mean([r["delta_probe_ctrl_ms"] for r in results])

    print("\n" + "=" * 80)
    print("FINAL EXPERIMENTAL SUMMARY")
    print("=" * 80)
    print(f"Nominal Splits (k^0): {k0_list}")
    print(f"Attacked Splits (k^a): {ka_list}")
    print(f"Manipulation Rate: {changed_rate:.1f}%")
    print(f"Direct Contention Slowdown (Delta_phys): {delta_phys_mean:.2f} ms")
    print(f"Control-Induced Damage (Delta^probe_ctrl): {delta_ctrl_mean:.2f} ms")

if __name__ == "__main__":
    main()
