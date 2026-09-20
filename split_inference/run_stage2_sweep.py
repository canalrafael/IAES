"""
Stage 2 Sweep Runner: Formal Attack Campaign
============================================
Systematically sweeps contention intensity, network conditions, and DNN models
to produce the quantitative results required for publication.

Parameter grid:
    workers:  [1, 2, 4, 6, 8]       — attacker thread count
    rtt_ms:   [5, 20, 50]            — one-way RTT (ms)
    bw_mbps:  [100, 50, 20]          — uplink bandwidth (Mbps)
    models:   ['resnet18', 'mobilenetv2']

Each cell runs N=20 trials (configurable). Results are saved to a CSV after
every cell (crash-safe). Use --quick for a 3-trial smoke test.

Usage:
    python -m split_inference.run_stage2_sweep
    python -m split_inference.run_stage2_sweep --quick
    python -m split_inference.run_stage2_sweep --trials 20 --models resnet18 mobilenetv2
    python -m split_inference.run_stage2_sweep --workers-range 1 8 --port 5006
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import torch

from split_inference.attack.stressor import MemoryContentionStressor
from split_inference.client import SplitInferenceClient
from split_inference.network.server import EdgeInferenceServer
from split_inference.run_gonogo_experiment import run_single_trial


# ─────────────────────────────────────────────────────────────────────────────
# Parameter grid
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WORKERS = [1, 2, 4, 6, 8]
DEFAULT_RTTS = [5.0, 20.0, 50.0]
DEFAULT_BWS = [100.0, 50.0, 20.0]
DEFAULT_MODELS = ["resnet18", "mobilenetv2"]
EDGE_SLOWDOWN = 4.0   # Pi 4 vs PC — same as Stage 1

RESULTS_DIR = "results"
FIGURES_DIR = os.path.join(RESULTS_DIR, "figures")


# ─────────────────────────────────────────────────────────────────────────────
# Model factory — returns (layer_info, model_class_name)
# ─────────────────────────────────────────────────────────────────────────────

def get_layer_info_for_model(model_name: str) -> Dict:
    if model_name == "resnet18":
        from split_inference.model.models import get_resnet18_layer_info
        return get_resnet18_layer_info()
    elif model_name == "mobilenetv2":
        from split_inference.model.models_mobilenet import get_mobilenetv2_layer_info
        return get_mobilenetv2_layer_info()
    else:
        raise ValueError(f"Unknown model: {model_name}")


def build_client(model_name: str, server_port: int, rtt_ms: float,
                 bw_mbps: float, slowdown: float) -> SplitInferenceClient:
    """Creates a SplitInferenceClient wired to the correct partitioned model."""
    layer_info = get_layer_info_for_model(model_name)

    if model_name == "resnet18":
        from split_inference.model.models import PartitionedResNet18
        model_cls = PartitionedResNet18
    else:
        from split_inference.model.models_mobilenet import PartitionedMobileNetV2
        model_cls = PartitionedMobileNetV2

    client = SplitInferenceClient(
        server_port=server_port,
        network_rtt_ms=rtt_ms,
        network_bw_mbps=bw_mbps,
        edge_slowdown_factor=slowdown,
        layer_info=layer_info,
    )
    # Swap the model inside the already-constructed client
    client.model = model_cls()
    client.model.eval()
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Single cell: N trials for one (model, workers, rtt, bw) combination
# ─────────────────────────────────────────────────────────────────────────────

def run_cell(
    model_name: str,
    workers: int,
    rtt_ms: float,
    bw_mbps: float,
    n_trials: int,
    server_port: int,
) -> List[Dict]:
    """Runs n_trials trials for one parameter cell. Returns list of result dicts."""
    cell_results = []
    
    for t in range(n_trials):
        trial = run_single_trial(
            server_port=server_port,
            stressor_workers=workers,
            nominal_rounds=40,
            attack_burst_rounds=12,
            eval_samples=15,
            network_rtt_ms=rtt_ms,
            network_bw_mbps=bw_mbps,
            edge_slowdown_factor=EDGE_SLOWDOWN,
        )
        trial.update({
            "model": model_name,
            "workers": workers,
            "rtt_ms": rtt_ms,
            "bw_mbps": bw_mbps,
            "trial": t + 1,
        })
        cell_results.append(trial)
        print(
            f"      trial {t+1}/{n_trials}: k^0={int(trial['k_0'])} "
            f"k^a={int(trial['k_a'])} "
            f"Δ_ctrl={trial['delta_probe_ctrl_ms']:+.1f}ms "
            f"{'✓' if trial['decision_changed'] else '✗'}"
        )
    return cell_results


# ─────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "model", "workers", "rtt_ms", "bw_mbps", "trial",
    "k_0", "k_a", "decision_changed",
    "J_k0_benign_ms", "J_k0_attacked_ms", "J_ka_benign_ms",
    "delta_phys_ms", "delta_probe_ctrl_ms",
]


def append_rows(csv_path: str, rows: List[Dict]) -> None:
    """Appends rows to CSV, creating it with a header if needed."""
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in CSV_FIELDS})


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stage 2: Formal Attack Campaign Sweep")
    parser.add_argument("--trials", type=int, default=20, help="Trials per cell (default 20)")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                        choices=["resnet18", "mobilenetv2"], help="Models to sweep")
    parser.add_argument("--workers-range", nargs=2, type=int, default=None,
                        metavar=("MIN", "MAX"),
                        help="Workers range inclusive (e.g. --workers-range 1 8)")
    parser.add_argument("--port", type=int, default=5005, help="Edge server port")
    parser.add_argument("--quick", action="store_true",
                        help="Smoke test: 3 trials, workers=[2,6], 1 network config")
    args = parser.parse_args()

    # Build parameter lists
    if args.quick:
        workers_list = [2, 6]
        rtts = [5.0]
        bws = [100.0]
        n_trials = 3
        print("=== QUICK SMOKE TEST MODE (3 trials per cell) ===")
    else:
        if args.workers_range:
            workers_list = list(range(args.workers_range[0], args.workers_range[1] + 1))
        else:
            workers_list = DEFAULT_WORKERS
        rtts = DEFAULT_RTTS
        bws = DEFAULT_BWS
        if args.quick:
            rtts = [rtts[0]]
            bws = [bws[0]]
        n_trials = args.trials

    # Build full grid
    grid = [
        (model, w, rtt, bw)
        for model in args.models
        for w in workers_list
        for rtt in rtts
        for bw in bws
    ]
    total_cells = len(grid)
    total_trials = total_cells * n_trials

    # Output path
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(RESULTS_DIR, f"raw_results_{timestamp}.csv")

    print("=" * 80)
    print("STAGE 2: FORMAL ATTACK CAMPAIGN SWEEP")
    print(f"  Models:  {args.models}")
    print(f"  Workers: {workers_list}")
    print(f"  RTTs:    {rtts} ms")
    print(f"  BWs:     {bws} Mbps")
    print(f"  Edge slowdown: {EDGE_SLOWDOWN}x  (Raspberry Pi 4 emulation)")
    print(f"  Trials per cell: {n_trials}")
    print(f"  Total cells: {total_cells}  |  Total trials: {total_trials}")
    print(f"  Results: {csv_path}")
    print("=" * 80)

    # Start edge server (shared across all cells)
    server = EdgeInferenceServer(host="127.0.0.1", port=args.port)
    server.start(background=True)
    time.sleep(1.0)

    all_results: List[Dict] = []
    try:
        for cell_idx, (model_name, workers, rtt_ms, bw_mbps) in enumerate(grid):
            print(
                f"\n[Cell {cell_idx+1}/{total_cells}] "
                f"model={model_name}  workers={workers}  "
                f"rtt={rtt_ms}ms  bw={bw_mbps}Mbps"
            )
            cell_rows = run_cell(
                model_name=model_name,
                workers=workers,
                rtt_ms=rtt_ms,
                bw_mbps=bw_mbps,
                n_trials=n_trials,
                server_port=args.port,
            )
            all_results.extend(cell_rows)

            # Persist immediately (crash-safe)
            append_rows(csv_path, cell_rows)

            # Cell summary
            success_rate = np.mean([r["decision_changed"] for r in cell_rows]) * 100
            delta_ctrl = np.mean([r["delta_probe_ctrl_ms"] for r in cell_rows])
            print(
                f"  → Success: {success_rate:.0f}%  "
                f"Δ_ctrl(mean): {delta_ctrl:+.1f} ms"
            )

    finally:
        server.stop()

    # Final aggregate summary
    print("\n" + "=" * 80)
    print("SWEEP COMPLETE")
    print(f"  Raw results saved to: {csv_path}")
    print(f"  Total trials completed: {len(all_results)}")

    overall_success = np.mean([r["decision_changed"] for r in all_results]) * 100
    overall_delta_ctrl = np.mean([r["delta_probe_ctrl_ms"] for r in all_results])
    print(f"  Overall manipulation rate: {overall_success:.1f}%")
    print(f"  Overall Δ_ctrl (mean):     {overall_delta_ctrl:+.1f} ms")
    print("=" * 80)
    print(f"\nRun analyze_results.py to generate paper figures:")
    print(f"  python -m split_inference.analyze_results --input {csv_path}")


if __name__ == "__main__":
    main()
